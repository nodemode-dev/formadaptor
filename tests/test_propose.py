import json
import subprocess

import pytest

from conftest import client, script

import propose
import spec

STANDIN = """import argparse, json, sys
from pathlib import Path
OUT = Path(__file__).resolve().parent.parent / "core" / "data" / "apps.json"
p = argparse.ArgumentParser(); p.add_argument("--family", required=True); p.add_argument("--check", action="store_true"); a = p.parse_args()
family = json.loads(Path(a.family).read_text())
text = json.dumps({"apps": [x["id"] for x in family["apps"] if x["public"]]}, indent=2) + "\\n"
current = OUT.read_text() if OUT.is_file() else ""
if a.check:
    print("in step" if current == text else "drifted: core/data/apps.json"); sys.exit(0 if current == text else 1)
OUT.parent.mkdir(parents=True, exist_ok=True); OUT.write_text(text)
"""

TARGET = {"name": "formx", "repository": "nodemode-dev/formX", "enabled": True, "command": ["python3", "-I", "setup/apps.py"],
          "files": ["core/data/apps.json"], "branch_prefix": "bot/formadaptor-"}


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
    assert plan["files"] == ["core/data/apps.json"]
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
    assert [t["name"] for t in json.loads(result.stdout)] == ["formmcp", "formskills", "profile"]


def test_a_bad_target_entry_is_refused(tmp_path):
    bad = dict(TARGET, command="python3 setup/apps.py; rm -rf /", files=["../x"])
    (tmp_path / "t.json").write_text(json.dumps({"format": "formadaptor-targets", "format_version": 1, "targets": [bad]}))
    with pytest.raises(propose.ProposeError, match="command must be a non-empty list of arguments; files must list plain paths"):
        propose.load_targets(tmp_path / "t.json")
