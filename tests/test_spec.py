import json

import pytest

from conftest import client

import registry
import spec

PUBLIC_KEYS = {"id", "public", "app", "repo", "repository", "site", "name", "kind", "summary", "licence", "state", "launcher", "agents", "release"}


def built(compiler, routes, generated="2026-11-19T00:00:00Z"):
    root, ids = compiler
    gh, fake = client(routes)
    return spec.build(root, gh, generated=generated, ids_path=ids), fake


def test_private_apps_are_a_bare_id_and_nothing_about_them_is_read(compiler, routes):
    doc, fake = built(compiler, routes)
    by_id = {a["id"]: a for a in doc["apps"]}
    assert [a["id"] for a in doc["apps"]] == ["formsecret", "formslide", "formvis"]
    assert by_id["formsecret"] == {"id": "formsecret", "public": False}
    assert "FormSecret" not in json.dumps(doc)
    assert [path for _, path, _ in fake.calls if "formSecret" in path] == ["/repos/nodemode-dev/formSecret"]


def test_public_apps_carry_ids_release_and_manifest_counts(compiler, routes):
    doc, _ = built(compiler, routes)
    by_id = {a["id"]: a for a in doc["apps"]}
    deck, vis = by_id["formslide"], by_id["formvis"]
    assert set(deck) == PUBLIC_KEYS
    assert (deck["app"], deck["repo"], deck["site"], deck["name"]) == ("formdeck", "formdeck", "formslide", "FormDeck")
    assert deck["release"]["version"] == "0.39.0"
    assert vis["release"]["skills"] == ["formvis-harness"]
    assert vis["manifest"]["skills"] == {"count": 1, "sub_skills": 3, "names": ["formvis-harness"]}
    assert doc["source"] == {"repository": "nodemode-dev/formcompiler", "registry_version": "0.16.0"}
    assert doc["content_sha256"] == spec.content_hash(doc)


def test_state_is_the_registry_catalog_state_whatever_the_release_says(compiler, routes):
    root, _ = compiler
    path = root / "apps" / "formvis.json"
    data = json.loads(path.read_text())
    data["catalog"]["state"] = "prelaunch"
    path.write_text(json.dumps(data))
    vis = {a["id"]: a for a in built(compiler, routes)[0]["apps"]}["formvis"]
    assert vis["state"] == "prelaunch"
    assert vis["release"]["version"] == "2.3.5" and vis["release"]["published"] == "2026-11-17T12:00:00Z"


def test_the_build_time_is_not_part_of_the_content_hash(compiler, routes):
    first, _ = built(compiler, routes, "2026-11-19T00:00:00Z")
    second, _ = built(compiler, routes, "2026-11-19T01:33:00Z")
    assert first["content_sha256"] == second["content_sha256"]
    assert spec.changes(first, second) == []


def test_an_app_that_has_just_gone_public_appears_and_names_the_title(compiler, routes):
    before, _ = built(compiler, routes)
    routes["/repos/nodemode-dev/formSecret"] = [200, {"private": False}]
    after, _ = built(compiler, routes)
    secret = {a["id"]: a for a in after["apps"]}["formsecret"]
    assert secret["public"] is True and secret["name"] == "FormSecret" and secret["release"] is None
    assert before["content_sha256"] != after["content_sha256"]
    assert spec.title(before, after) == "chore(family): FormSecret is public"
    assert spec.title(after, before) == "chore(family): formsecret is no longer public"


def test_the_title_counts_what_it_does_not_show():
    old = {"apps": [{"id": f"a{i}", "public": True, "name": f"A{i}", "release": {"version": "1.0.0"}} for i in range(5)]}
    new = {"apps": [{"id": f"a{i}", "public": True, "name": f"A{i}", "release": {"version": "1.1.0"}} for i in range(5)]}
    assert spec.title(old, new) == "chore(family): A0 1.1.0, A1 1.1.0, A2 1.1.0 and 2 more"
    assert spec.title(None, new) == "chore(family): follow the family spec"


def test_the_build_stops_when_the_id_pairs_are_out_of_step(compiler, routes):
    root, ids = compiler
    (root / "apps" / "formnew.json").write_text((root / "apps" / "formvis.json").read_text().replace("formvis", "formnew"))
    with pytest.raises(registry.RegistryError, match="formnew: in the registry, not in spec/ids.json"):
        spec.build(root, client(routes)[0], ids_path=ids)


class Branch:
    def __init__(self):
        self.ref = None
        self.objects = {}
        self.count = 0

    def __call__(self, method, url, headers, data):
        path = url.split("http://fake", 1)[1]
        body = json.loads(data) if data else None
        if method == "GET" and path.endswith("/git/ref/heads/spec"):
            return (200, {}, json.dumps({"object": {"sha": self.ref}}).encode()) if self.ref else (404, {}, b"{}")
        if method == "GET" and "/git/commits/" in path:
            return 200, {}, json.dumps({"parents": [{"sha": p} for p in self.objects[path.rsplit("/", 1)[1]]["parents"]]}).encode()
        if method == "GET" and "/contents/family.json?ref=" in path:
            return 200, {}, json.dumps({"encoding": "base64", "content": self.objects[path.split("ref=")[1]]["content"]}).encode()
        self.count += 1
        sha = f"{self.count:040x}"
        if path.endswith("/git/blobs"):
            self.objects[sha] = {"content": body["content"]}
        elif path.endswith("/git/trees"):
            self.objects[sha] = {"content": self.objects[body["tree"][0]["sha"]]["content"]}
        elif path.endswith("/git/commits"):
            self.objects[sha] = {"content": self.objects[body["tree"]]["content"], "parents": body["parents"]}
        else:
            self.ref = body["sha"]
            return 200, {}, b"{}"
        return 201, {}, json.dumps({"sha": sha}).encode()


def test_publish_then_fetch_gives_the_spec_and_the_one_before(compiler, routes, tmp_path):
    before, _ = built(compiler, routes)
    routes["/repos/nodemode-dev/formSecret"] = [200, {"private": False}]
    after, _ = built(compiler, routes)
    import github_api
    branch = Branch()
    gh = github_api.GitHub(base="http://fake", token="t", transport=branch)
    assert spec.fetch(gh, spec.SELF, "spec", tmp_path / "none.json") == ""
    first = spec.publish(gh, spec.SELF, "spec", spec.text_of(before), before)
    assert branch.objects[first]["parents"] == []
    second = spec.publish(gh, spec.SELF, "spec", spec.text_of(after), after)
    assert branch.objects[second]["parents"] == [first] and branch.ref == second
    assert spec.fetch(gh, spec.SELF, "spec", tmp_path / "now.json", tmp_path / "was.json") == second
    assert json.loads((tmp_path / "now.json").read_text()) == after
    assert json.loads((tmp_path / "was.json").read_text()) == before
