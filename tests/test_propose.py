import json
import subprocess

import pytest

from conftest import client, script

import propose
import spec

STANDIN = """import argparse, json, shutil, sys
from pathlib import Path
OUT = Path(__file__).resolve().parent.parent / "core" / "data" / "apps.json"
KEPT = Path(__file__).resolve().parent / "family.spec.json"
p = argparse.ArgumentParser(); p.add_argument("--family", required=True); p.add_argument("--check", action="store_true"); a = p.parse_args()
family = json.loads(Path(a.family).read_text())
text = json.dumps({"apps": [x["id"] for x in family["apps"] if x["public"]]}, indent=2) + "\\n"
current = OUT.read_text() if OUT.is_file() else ""
if a.check:
    print("in step" if current == text else "drifted: core/data/apps.json"); sys.exit(0 if current == text else 1)
if current != text:
    OUT.parent.mkdir(parents=True, exist_ok=True); OUT.write_text(text); shutil.copyfile(a.family, KEPT)
"""

TARGET = {"name": "formx", "repository": "nodemode-dev/formX", "enabled": True, "command": ["python3", "-I", "setup/apps.py"],
          "files": ["core/data/apps.json", "setup/family.spec.json"], "spec_copy": "setup/family.spec.json", "branch_prefix": "bot/formadaptor-"}


def family_with_version(tmp_path, version, name):
    path = family(tmp_path, ["formvis"], name)
    doc = json.loads(path.read_text())
    doc["apps"][0]["release"] = {"version": version}
    doc["content_sha256"] = spec.content_hash(doc)
    path.write_text(spec.text_of(doc))
    return path


def git(path, *args):
    return subprocess.run(["git", "-C", str(path), *args], check=True, capture_output=True, text=True).stdout


def family(tmp_path, ids, name="family.json"):
    doc = {"format": spec.FORMAT, "format_version": 1, "generated": "2026-11-19T00:00:00Z",
           "source": {"repository": "nodemode-dev/formcompiler", "registry_version": "0.16.0"}, "content_sha256": "",
           "apps": [{"id": i, "public": True, "name": i.capitalize(), "release": None} for i in ids] + [{"id": "formhidden", "public": False}]}
    doc["content_sha256"] = spec.content_hash(doc)
    path = tmp_path / name
    path.write_text(spec.text_of(doc))
    return path


@pytest.fixture
def target(tmp_path):
    repo = tmp_path / "target"
    (repo / "setup").mkdir(parents=True)
    (repo / "setup" / "apps.py").write_text(STANDIN)
    git(repo, "init", "-q", "-b", "main")
    git(repo, "-c", "user.name=t", "-c", "user.email=t@t", "add", "-A")
    git(repo, "-c", "user.name=t", "-c", "user.email=t@t", "commit", "-q", "-m", "init")
    return repo


def test_a_difference_is_planned_with_branch_files_and_title(tmp_path, target):
    before = family(tmp_path, ["formvis"], "before.json")
    after = family(tmp_path, ["formvis", "formnew"])
    plan = propose.plan(TARGET, target, after, before)
    assert plan["files"] == ["core/data/apps.json", "setup/family.spec.json"]
    assert (target / "setup" / "family.spec.json").read_bytes() == after.read_bytes()
    assert "- `setup/family.spec.json` (the copy of the spec it was generated from)" in plan["body"]
    assert plan["branch"] == f"bot/formadaptor-{propose.change_hash(target, plan['files'])[:10]}"
    assert plan["title"] == "chore(family): Formnew joins the family"
    assert "formhidden" not in (target / "core" / "data" / "apps.json").read_text()


def test_nothing_is_proposed_when_the_target_is_in_step(tmp_path, target):
    path = family(tmp_path, ["formvis"])
    propose.plan(TARGET, target, path)
    git(target, "add", "-A")
    git(target, "-c", "user.name=t", "-c", "user.email=t@t", "commit", "-q", "-m", "generated")
    assert propose.plan(TARGET, target, path) is None
    assert git(target, "status", "--porcelain") == ""


def test_a_spec_change_that_leaves_the_output_alone_proposes_nothing(tmp_path, target):
    propose.plan(TARGET, target, family_with_version(tmp_path, "1.0.0", "one.json"))
    git(target, "add", "-A")
    git(target, "-c", "user.name=t", "-c", "user.email=t@t", "commit", "-q", "-m", "generated")
    assert propose.plan(TARGET, target, family_with_version(tmp_path, "1.0.1", "two.json")) is None
    assert git(target, "status", "--porcelain") == ""


RECORDS_THE_REGISTRY = STANDIN.replace('json.dumps({"apps"', 'json.dumps({"version": family["source"]["registry_version"], "apps"')


def family_from_registry(tmp_path, ids, registry, generated, name):
    path = family(tmp_path, ids, name)
    doc = json.loads(path.read_text())
    doc["source"]["registry_version"] = registry
    doc["generated"] = generated
    doc["content_sha256"] = spec.content_hash(doc)
    path.write_text(spec.text_of(doc))
    return path


def generated_and_committed(target, path):
    propose.plan(TARGET, target, path)
    git(target, "add", "-A")
    git(target, "-c", "user.name=t", "-c", "user.email=t@t", "commit", "-q", "-m", "generated")


def test_specs_that_differ_only_in_registry_version_time_and_hash_propose_nothing(tmp_path, target):
    one = family_from_registry(tmp_path, ["formvis"], "0.16.0", "2026-11-19T00:00:00Z", "one.json")
    two = family_from_registry(tmp_path, ["formvis"], "0.16.1", "2026-11-19T07:00:00Z", "two.json")
    before, after = json.loads(one.read_text()), json.loads(two.read_text())
    assert sorted(k for k in before if before[k] != after[k]) == ["content_sha256", "generated", "source"]
    assert before["source"]["repository"] == after["source"]["repository"]
    generated_and_committed(target, one)
    kept = (target / "setup" / "family.spec.json").read_bytes()
    assert propose.plan(TARGET, target, two, one) is None
    assert git(target, "status", "--porcelain") == ""
    assert (target / "setup" / "family.spec.json").read_bytes() == kept == one.read_bytes()


def test_an_output_that_records_the_registry_version_is_warned_about_and_still_proposed(tmp_path, target):
    assert RECORDS_THE_REGISTRY != STANDIN
    (target / "setup" / "apps.py").write_text(RECORDS_THE_REGISTRY)
    git(target, "-c", "user.name=t", "-c", "user.email=t@t", "commit", "-qam", "records the registry version")
    one = family_from_registry(tmp_path, ["formvis"], "0.16.0", "2026-11-19T00:00:00Z", "one.json")
    generated_and_committed(target, one)
    plan = propose.plan(TARGET, target, family_from_registry(tmp_path, ["formvis"], "0.16.1", "2026-11-19T07:00:00Z", "two.json"), one)
    assert plan["files"] == ["core/data/apps.json", "setup/family.spec.json"]
    assert plan["warning"].startswith("formx: core/data/apps.json differs although")
    assert "its generator is recording something that is not app data" in plan["warning"]
    git(target, "checkout", "-q", "--", ".")
    joined = propose.plan(TARGET, target, family_from_registry(tmp_path, ["formvis", "formnew"], "0.16.1", "2026-11-19T07:00:00Z", "three.json"), one)
    assert joined["files"] == plan["files"] and joined["warning"] is None


def test_the_warning_reaches_the_run_summary_and_the_run_does_not_fail(tmp_path, target):
    (target / "setup" / "apps.py").write_text(RECORDS_THE_REGISTRY)
    git(target, "-c", "user.name=t", "-c", "user.email=t@t", "commit", "-qam", "records the registry version")
    one = family_from_registry(tmp_path, ["formvis"], "0.16.0", "2026-11-19T00:00:00Z", "one.json")
    generated_and_committed(target, one)
    two = family_from_registry(tmp_path, ["formvis"], "0.16.1", "2026-11-19T07:00:00Z", "two.json")
    (tmp_path / "t.json").write_text(json.dumps({"format": "formadaptor-targets", "format_version": 1, "targets": [TARGET]}))
    shown, out = tmp_path / "summary.md", tmp_path / "output"
    result = script("propose.py", "run", "--target", "formx", "--checkout", str(target), "--family", str(two), "--dry-run", "--targets", str(tmp_path / "t.json"),
                    env={"PATH": "/usr/bin:/bin", "GITHUB_STEP_SUMMARY": str(shown), "GITHUB_OUTPUT": str(out)})
    assert result.returncode == 0
    assert shown.read_text().startswith("Warning: formx: core/data/apps.json differs although")
    assert "is recording something that is not app data (docs/TARGETS.md). The proposal is not held back.\n" in shown.read_text()
    assert "::warning::formx: core/data/apps.json differs" in result.stdout
    assert '"branch": "bot/formadaptor-' in result.stdout


def test_a_generator_that_changes_only_its_copy_proposes_nothing(tmp_path, target, capsys):
    (target / "setup" / "apps.py").write_text("import shutil, sys\nif '--check' in sys.argv: sys.exit(1)\n"
                                              "shutil.copyfile(sys.argv[sys.argv.index('--family') + 1], 'setup/family.spec.json')\n")
    git(target, "-c", "user.name=t", "-c", "user.email=t@t", "commit", "-qam", "copy only")
    assert propose.plan(TARGET, target, family(tmp_path, ["formvis"])) is None
    assert "changed only setup/family.spec.json" in capsys.readouterr().out


def test_a_generator_that_does_not_refresh_its_copy_is_refused(tmp_path, target):
    (target / "setup" / "apps.py").write_text(STANDIN.replace("; shutil.copyfile(a.family, KEPT)", ""))
    git(target, "-c", "user.name=t", "-c", "user.email=t@t", "commit", "-qam", "no copy")
    with pytest.raises(propose.ProposeError, match="did not leave setup/family.spec.json a copy of the spec"):
        propose.plan(TARGET, target, family(tmp_path, ["formvis"]))


def test_a_target_without_its_spec_copy_among_its_files_is_refused(tmp_path):
    bad = dict(TARGET, files=["core/data/apps.json"])
    (tmp_path / "t.json").write_text(json.dumps({"format": "formadaptor-targets", "format_version": 1, "targets": [bad]}))
    with pytest.raises(propose.ProposeError, match="spec_copy must name"):
        propose.load_targets(tmp_path / "t.json")


def test_a_file_outside_the_declared_list_is_refused(tmp_path, target):
    (target / "setup" / "apps.py").write_text(STANDIN + "\nif not a.check: Path(OUT.parent.parent.parent / 'stray.txt').write_text('x')\n")
    git(target, "-c", "user.name=t", "-c", "user.email=t@t", "commit", "-qam", "stray")
    with pytest.raises(propose.ProposeError, match="outside its declared list: stray.txt"):
        propose.plan(TARGET, target, family(tmp_path, ["formvis"]))


def test_a_check_that_crashes_is_not_a_difference(tmp_path, target):
    (target / "setup" / "apps.py").write_text("import sys\nsys.exit(2)\n")
    git(target, "-c", "user.name=t", "-c", "user.email=t@t", "commit", "-qam", "broken")
    with pytest.raises(propose.ProposeError, match="exited 2, not 0 or 1"):
        propose.plan(TARGET, target, family(tmp_path, ["formvis"]))


def test_the_generator_does_not_see_the_token(tmp_path, target, monkeypatch):
    monkeypatch.setenv("FORMADAPTOR_TARGET_TOKEN", "secret")
    monkeypatch.setenv("GH_TOKEN", "secret")
    assert not {"FORMADAPTOR_TARGET_TOKEN", "GH_TOKEN", "GITHUB_TOKEN"} & set(propose.generator_env())


def test_propose_pushes_opens_and_supersedes(tmp_path, target, monkeypatch):
    remote = tmp_path / "remote" / "nodemode-dev" / "formX.git"
    remote.parent.mkdir(parents=True)
    subprocess.run(["git", "init", "-q", "--bare", str(remote)], check=True)
    monkeypatch.setenv("FORMADAPTOR_GIT_BASE", f"file://{tmp_path / 'remote'}")
    plan = propose.plan(TARGET, target, family(tmp_path, ["formvis"]))
    older = {"number": 7, "head": {"ref": "bot/formadaptor-0000000000", "repo": {"full_name": "nodemode-dev/formX"}}}
    other = {"number": 8, "head": {"ref": "feature/x", "repo": {"full_name": "nodemode-dev/formX"}}}
    gh, fake = client({
        "/repos/nodemode-dev/formX/pulls?state=open&base=main": [200, [older, other]],
        ("POST", "/repos/nodemode-dev/formX/pulls"): [201, {"number": 9}],
        ("POST", "/repos/nodemode-dev/formX/issues/7/comments"): [201, {}],
        ("PATCH", "/repos/nodemode-dev/formX/pulls/7"): [200, {}],
        ("DELETE", "/repos/nodemode-dev/formX/git/refs/heads/bot/formadaptor-0000000000"): [204, b""],
    })
    pull, closed = propose.propose(gh, target, TARGET, plan, "secret-token")
    assert pull["number"] == 9 and closed == [7]
    sent = [(m, p) for m, p, _ in fake.calls]
    assert ("POST", "/repos/nodemode-dev/formX/issues/7/comments") in sent and ("PATCH", "/repos/nodemode-dev/formX/pulls/7") in sent
    assert not any("/8" in p for _, p in sent)
    assert git(remote, "log", plan["branch"], "-1", "--format=%an <%ae> %s") == f"nodemode-ai <mackin@nodemode.ai> {plan['title']}\n"
    assert "secret-token" not in (target / ".git" / "config").read_text()


def test_an_open_pull_request_for_the_same_change_stops_a_second_push(tmp_path, target):
    plan = propose.plan(TARGET, target, family(tmp_path, ["formvis"]))
    same = {"number": 9, "head": {"ref": plan["branch"], "repo": {"full_name": "nodemode-dev/formX"}}}
    gh, fake = client({"/repos/nodemode-dev/formX/pulls?state=open&base=main": [200, [same]]})
    assert propose.propose(gh, target, TARGET, plan, "t") == (None, [])
    assert [m for m, _, _ in fake.calls] == ["GET"]


def test_the_targets_file_loads_and_lists_the_enabled_ones():
    result = script("propose.py", "matrix")
    assert result.returncode == 0
    assert [t["name"] for t in json.loads(result.stdout)] == ["formmcp", "formskills", "formext", "formai-templates"]


def test_a_disabled_target_is_a_skip_not_a_failure(tmp_path):
    named = {t["name"]: t for t in propose.load_targets()}
    assert named["profile"]["enabled"] is False
    out = tmp_path / "output"
    result = script("propose.py", "run", "--target", "profile", "--checkout", str(tmp_path / "no-checkout"), "--family", str(tmp_path / "no-family.json"),
                    env={"PATH": "/usr/bin:/bin", "GITHUB_OUTPUT": str(out)})
    assert result.returncode == 0
    assert "disabled in targets.json, nothing to do" in result.stdout
    assert out.read_text() == "proposed=false\n"


def test_form_ext_names_the_files_its_generator_writes():
    target = {t["name"]: t for t in propose.load_targets()}["formext"]
    assert target["enabled"] is True
    assert target["files"] == [".claude/skills/HOSTS.md", "setup/hosts.json", "setup/family.spec.json"]
    assert target["spec_copy"] == "setup/family.spec.json"


def test_a_bad_target_entry_is_refused(tmp_path):
    bad = dict(TARGET, command="python3 setup/apps.py; rm -rf /", files=["../x"])
    (tmp_path / "t.json").write_text(json.dumps({"format": "formadaptor-targets", "format_version": 1, "targets": [bad]}))
    with pytest.raises(propose.ProposeError, match="command must be a non-empty list of arguments; files must list plain paths"):
        propose.load_targets(tmp_path / "t.json")


STANDIN_GIT = """#!/usr/bin/env python3
import json, os, sys
from pathlib import Path
with open(LOG, "a") as log:
    log.write(json.dumps({"argv": sys.argv[1:], "env": sorted(os.environ)}) + "\\n")
Path(sys.argv[-1]).mkdir(parents=True)
"""


def apps_family(tmp_path):
    doc = {"format": spec.FORMAT, "format_version": 1, "generated": "2026-11-22T00:00:00Z",
           "source": {"repository": "nodemode-dev/formcompiler", "registry_version": "0.16.1"}, "content_sha256": "",
           "apps": [{"id": "formext", "public": True, "repo": "form.ext", "repository": "nodemode-dev/form.ext", "release": {"version": "0.10.0", "tag": "v0.10.0"}},
                    {"id": "formhidden", "public": False},
                    {"id": "formnew", "public": True, "repo": "formnew", "repository": "nodemode-dev/formnew", "release": None},
                    {"id": "formtxt", "public": True, "repo": "formtxt", "repository": "nodemode-dev/formtxt", "release": {"version": "0.38.0", "tag": "v0.38.0"}}]}
    doc["content_sha256"] = spec.content_hash(doc)
    path = tmp_path / "family.json"
    path.write_text(spec.text_of(doc))
    return path


def test_the_templates_target_reads_each_app_at_its_released_tag_beside_its_checkout():
    target = {t["name"]: t for t in propose.load_targets()}["formai-templates"]
    assert target["enabled"] is True and target["repository"] == "nodemode-dev/formai-templates"
    assert target["command"] == ["python3", "-I", "scripts/collect.py", "--apps-root", "../formai-templates-apps"]
    assert target["app_checkouts"] == "../formai-templates-apps"
    assert target["files"] == ["apps/", "index.json", "scripts/family.spec.json"] and target["spec_copy"] == "scripts/family.spec.json"


def test_app_checkouts_are_public_released_apps_at_their_tags_with_no_token(tmp_path, monkeypatch):
    bin_dir = tmp_path / "bin"
    bin_dir.mkdir()
    log = tmp_path / "git.log"
    (bin_dir / "git").write_text(STANDIN_GIT.replace("LOG,", f"{str(log)!r},"))
    (bin_dir / "git").chmod(0o755)
    monkeypatch.setenv("PATH", f"{bin_dir}:/usr/bin:/bin")
    monkeypatch.setenv("FORMADAPTOR_TARGET_TOKEN", "secret")
    monkeypatch.setenv("GH_TOKEN", "secret")
    monkeypatch.delenv("FORMADAPTOR_GIT_BASE", raising=False)
    (tmp_path / "target").mkdir()
    target = dict(TARGET, app_checkouts="../apps")
    fetched = propose.fetch_apps(target, tmp_path / "target", spec.load(apps_family(tmp_path)))
    assert fetched == ["form.ext", "formtxt"]
    calls = [json.loads(line) for line in log.read_text().splitlines()]
    assert [c["argv"][-4:] for c in calls] == [
        ["v0.10.0", "--", "https://github.com/nodemode-dev/form.ext.git", str(tmp_path / "apps" / "form.ext")],
        ["v0.38.0", "--", "https://github.com/nodemode-dev/formtxt.git", str(tmp_path / "apps" / "formtxt")],
    ]
    assert all({"clone", "--depth", "--single-branch", "--branch"} <= set(c["argv"]) and "core.hooksPath=/dev/null" in c["argv"] for c in calls)
    assert all(not {"FORMADAPTOR_TARGET_TOKEN", "GH_TOKEN", "GITHUB_TOKEN"} & set(c["env"]) for c in calls)


def test_app_checkouts_go_only_into_a_new_folder_beside_the_checkout(tmp_path):
    for inside in ("apps", "../..", "../a/b", "/tmp/apps"):
        (tmp_path / "t.json").write_text(json.dumps({"format": "formadaptor-targets", "format_version": 1, "targets": [dict(TARGET, app_checkouts=inside)]}))
        with pytest.raises(propose.ProposeError, match="app_checkouts must be one folder beside the checkout"):
            propose.load_targets(tmp_path / "t.json")
    (tmp_path / "apps" / "kept").mkdir(parents=True)
    with pytest.raises(propose.ProposeError, match="is not empty"):
        propose.fetch_apps(dict(TARGET, app_checkouts="../apps"), tmp_path / "target", spec.load(apps_family(tmp_path)))
    assert (tmp_path / "apps" / "kept").is_dir()


def test_a_target_without_app_checkouts_needs_none(tmp_path):
    result = script("propose.py", "checkouts", "--target", "formmcp", "--checkout", str(tmp_path), "--family", str(tmp_path / "no-family.json"))
    assert result.returncode == 0 and "formmcp: needs no app checkouts" in result.stdout


def test_a_long_list_of_changed_files_is_cut_in_the_body_and_keeps_the_copy():
    doc = json.loads(spec.text_of({"content_sha256": "0" * 64, "source": {"registry_version": "0.16.1"}}))
    paths = [f"apps/formx/demos/d{i:03}.zip" for i in range(120)] + ["scripts/family.spec.json"]
    body = propose.body_of(dict(TARGET, spec_copy="scripts/family.spec.json"), doc, None, paths)
    assert body.count("\n- `") == propose.LISTED
    assert "- `scripts/family.spec.json` (the copy of the spec it was generated from)" in body
    assert f"- and {len(paths) - propose.LISTED} more files" in body
