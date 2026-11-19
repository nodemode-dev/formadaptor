import json

import pytest

from conftest import FIXTURES, REPO, client, contents, script

import github_api
import manifest
import registry
import releases
import visibility


def test_ids_file_pairs_every_registry_entry_once():
    rows = json.loads((REPO / "spec" / "ids.json").read_text(encoding="utf-8"))["apps"]
    by_app = {r["app"]: r for r in rows}
    assert len(rows) == len(by_app) == 32
    assert by_app["formdeck"]["catalog"] == by_app["formdeck"]["site"] == "formslide"
    assert by_app["formportal"]["catalog"] == "formai"
    assert by_app["formrec"]["repo"] == "formREC"
    assert by_app["formCAD"] == {"app": "formCAD", "repo": "formCAD", "catalog": "formcad", "site": "formcad"}
    assert len({r["catalog"] for r in rows}) == 32


def test_id_check_names_a_changed_catalogue_id(compiler):
    root, ids = compiler
    entries = registry.load(root)
    assert registry.id_problems(entries, ids) == []
    data = json.loads((root / "apps" / "formdeck.json").read_text())
    data["catalog"]["id"] = "formdeck"
    (root / "apps" / "formdeck.json").write_text(json.dumps(data))
    assert registry.id_problems(registry.load(root), ids) == ["formdeck: catalog is 'formdeck' in the registry, 'formslide' in spec/ids.json"]


def test_registry_refuses_a_folder_that_is_not_a_checkout(tmp_path):
    result = script("registry.py", "ids", "--compiler", str(tmp_path), "--check")
    assert result.returncode == 1 and "not formcompiler's registry folder" in result.stderr


@pytest.mark.parametrize("answer, expected", [
    ([200, {"private": False}], True),
    ([200, {"private": True}], False),
    ([200, {}], False),
    ([404, {"message": "Not Found"}], False),
    ([401, {}], False),
    ([403, {}], False),
])
def test_visibility_is_public_only_for_200_with_private_false(answer, expected):
    gh, _ = client({"/repos/nodemode-dev/formx": answer})
    assert visibility.public(gh, "formx") is expected


@pytest.mark.parametrize("answer", [[500, {}], [503, {}], [429, {}], [403, {}, {"X-RateLimit-Remaining": "0"}]])
def test_visibility_stops_when_github_does_not_answer(answer):
    gh, _ = client({"/repos/nodemode-dev/formx": answer})
    with pytest.raises(github_api.ApiError):
        visibility.public(gh, "formx")


def test_newest_skips_drafts_prereleases_and_yanked_versions(routes):
    listed = routes["/repos/nodemode-dev/formvis/releases"][1]
    assert releases.newest(listed, "formvis")[0] == "2.3.5"
    assert releases.newest(listed, "formvis", frozenset({("formvis", "2.3.5")}))[0] == "1.99.9"
    assert releases.newest([{"tag_name": "v2.10.0"}, {"tag_name": "v2.9.9"}], "formvis")[0] == "2.10.0"


def test_latest_reads_the_release_and_its_skills(routes):
    gh, _ = client(routes)
    block = releases.latest(gh, "formvis", "formvis")
    assert block == {"version": "2.3.5", "tag": "v2.3.5", "published": "2026-11-17T12:00:00Z",
                     "url": "https://github.com/nodemode-dev/formvis/releases/tag/v2.3.5", "skills": ["formvis-harness"]}
    assert releases.latest(gh, "formnone", "formnone") is None


def test_a_form_app_json_for_another_version_gives_no_skills(routes, capsys):
    routes["/dl/formvis/form-app.json"] = [200, {"app": "formvis", "version": "2.3.4"}]
    gh, _ = client(routes)
    assert "skills" not in releases.latest(gh, "formvis", "formvis")
    assert "names formvis 2.3.4" in capsys.readouterr().out


def test_yanked_rows_are_read_from_formcompiler(compiler):
    assert releases.load_yanked(compiler[0]) == frozenset({("formdeck", "0.40.0")})


def test_the_sample_manifest_passes_and_counts():
    doc = json.loads((FIXTURES / "manifest.formvis.json").read_text())
    assert manifest.problems_of(doc, "formvis") == []
    assert manifest.counts(doc) == {
        "mcp": {"tools": 4, "read_only": 1, "approval_gated": 1, "transports": ["http", "stdio"]},
        "skills": {"count": 1, "sub_skills": 3, "names": ["formvis-harness"]},
        "dock": {"present": True, "positions": ["right", "bottom"], "tabs": 2},
        "extensions": {"host_api": "1"},
    }
    assert script("manifest.py", "check", str(FIXTURES / "manifest.formvis.json"), "--app", "formvis").returncode == 0


def test_a_broken_manifest_names_each_problem():
    doc = json.loads((FIXTURES / "manifest.formvis.json").read_text())
    doc["extra"] = 1
    doc["mcp"]["read_only"].append("nope")
    doc["dock"]["positions"] = ["top"]
    found = manifest.problems_of(doc, "formcut")
    assert found == [
        "manifest.extra is not a manifest field",
        "app is 'formvis', the registry name is 'formcut'",
        "mcp.read_only names 'nope', which is not in mcp.tools",
        "dock.positions must list left, right, bottom or floating, each once",
    ]


def test_an_app_without_mcp_or_extensions_is_valid():
    doc = json.loads((FIXTURES / "manifest.formvis.json").read_text())
    doc["mcp"] = None
    doc["extensions"] = None
    assert manifest.problems_of(doc) == []
    assert manifest.counts(doc)["mcp"] is None


def dispatching():
    doc = json.loads((FIXTURES / "manifest.formvis.json").read_text())
    doc["mcp"]["dispatch"] = [{"tool": "apply_filter", "reaches": 289}]
    return doc


def test_a_manifest_with_dispatch_passes_and_its_counts_carry_it():
    doc = dispatching()
    assert manifest.problems_of(doc, "formvis") == []
    assert manifest.counts(doc)["mcp"] == {
        "tools": 4, "read_only": 1, "approval_gated": 1, "transports": ["http", "stdio"],
        "dispatch": [{"tool": "apply_filter", "reaches": 289}],
    }
    schema = json.loads((REPO / "spec" / "agent-manifest.schema.json").read_text())
    assert schema["properties"]["mcp"]["oneOf"][1]["properties"]["dispatch"]["items"]["required"] == ["tool", "reaches"]
    assert "dispatch" not in schema["properties"]["mcp"]["oneOf"][1]["required"]


def test_a_manifest_without_dispatch_counts_exactly_as_before():
    doc = json.loads((FIXTURES / "manifest.formvis.json").read_text())
    assert "dispatch" not in manifest.counts(doc)["mcp"]


@pytest.mark.parametrize("rows, problem", [
    ([], "mcp.dispatch must be a non-empty list, or left out"),
    ("run_command", "mcp.dispatch must be a non-empty list, or left out"),
    ([{"tool": "nope", "reaches": 3}], "mcp.dispatch[0].tool names 'nope', which is not in mcp.tools"),
    ([{"tool": "apply_filter", "reaches": 0}], "mcp.dispatch[0].reaches must be a whole number of at least 1"),
    ([{"tool": "apply_filter", "reaches": True}], "mcp.dispatch[0].reaches must be a whole number of at least 1"),
    ([{"tool": "apply_filter", "reaches": 2.5}], "mcp.dispatch[0].reaches must be a whole number of at least 1"),
    ([{"tool": "apply_filter", "reaches": 2}, {"tool": "apply_filter", "reaches": 3}], "mcp.dispatch[1].tool 'apply_filter' is listed twice"),
    ([{"tool": "apply_filter"}], "mcp.dispatch[0].reaches is missing"),
    ([{"tool": "apply_filter", "reaches": 2, "note": "x"}], "mcp.dispatch[0].note is not a manifest field"),
])
def test_a_bad_dispatch_names_the_problem(rows, problem):
    doc = dispatching()
    doc["mcp"]["dispatch"] = rows
    assert manifest.problems_of(doc, "formvis") == [problem]


def test_dispatch_is_not_allowed_beside_other_unknown_fields():
    doc = dispatching()
    doc["mcp"]["extra"] = 1
    assert manifest.problems_of(doc) == ["mcp.extra is not a manifest field"]


def test_manifest_read_missing_broken_and_down(routes, capsys):
    gh, _ = client(routes)
    assert manifest.read(gh, "formvis", "v2.3.5", "formvis")["mcp"]["tools"] == 4
    assert manifest.read(gh, "formdeck", "v0.39.0", "formdeck") is None
    assert capsys.readouterr().out == ""
    routes["/repos/nodemode-dev/formdeck/contents/agents/manifest.json?ref=v0.39.0"] = contents("{not json")
    assert manifest.read(gh, "formdeck", "v0.39.0", "formdeck") is None
    assert "is not JSON" in capsys.readouterr().out
    routes["/repos/nodemode-dev/formdeck/contents/agents/manifest.json?ref=v0.39.0"] = [502, {}]
    with pytest.raises(github_api.ApiError):
        manifest.read(gh, "formdeck", "v0.39.0", "formdeck")
