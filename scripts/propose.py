import argparse
import base64
import hashlib
import json
import os
import re
import subprocess
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import spec
from github_api import ApiError, GitHub, output, summary

ROOT = Path(__file__).resolve().parent.parent
TARGETS = ROOT / "targets.json"
NAME = re.compile(r"^[a-z0-9][a-z0-9-]{0,39}$")
REPOSITORY = re.compile(r"^nodemode-dev/[A-Za-z0-9._-]+$")
PREFIX = re.compile(r"^bot/[a-z0-9-]+-$")
FILE = re.compile(r"^[A-Za-z0-9._-]+(/[A-Za-z0-9._-]+)*/?$")
BASE = "main"
IDENTITY = ("nodemode-ai", "mackin@nodemode.ai")
GENERATOR_TIMEOUT = 600


class ProposeError(Exception):
    pass


def load_targets(path=TARGETS):
    data = json.loads(Path(path).read_text(encoding="utf-8"))
    targets = data.get("targets") if isinstance(data, dict) else None
    if data.get("format") != "formadaptor-targets" or not isinstance(targets, list):
        raise ProposeError(f"{Path(path).name} is not a formadaptor-targets file")
    seen = set()
    for target in targets:
        name = target.get("name", "")
        problems = []
        if not NAME.match(name) or name in seen:
            problems.append("name must be a unique short name")
        if not REPOSITORY.match(target.get("repository", "")):
            problems.append("repository must be nodemode-dev/<repo>")
        if not isinstance(target.get("enabled"), bool):
            problems.append("enabled must be true or false")
        command = target.get("command")
        if not isinstance(command, list) or not command or not all(isinstance(c, str) and c for c in command):
            problems.append("command must be a non-empty list of arguments")
        files = target.get("files")
        if not isinstance(files, list) or not files or not all(isinstance(f, str) and FILE.match(f) and ".." not in f.split("/") for f in files):
            problems.append("files must list plain paths in the target repository")
        elif not isinstance(target.get("spec_copy"), str) or target["spec_copy"] not in files:
            problems.append("spec_copy must name the target's copy of the spec, one of its files")
        if not PREFIX.match(target.get("branch_prefix", "")):
            problems.append("branch_prefix must look like bot/<name>-")
        if problems:
            raise ProposeError(f"target {name or '?'}: {'; '.join(problems)}")
        seen.add(name)
    return targets


def find(targets, name):
    for target in targets:
        if target["name"] == name:
            return target
    raise ProposeError(f"no target named {name!r} in targets.json")


def allowed(path, files):
    return any(path == f or (f.endswith("/") and path.startswith(f)) for f in files)


def git(checkout, *args, env=None):
    result = subprocess.run(["git", "-C", str(checkout), *args], capture_output=True, text=True, env=env)
    if result.returncode != 0:
        raise ProposeError(f"git {' '.join(args[:2])}: {result.stderr.strip()[:300]}")
    return result.stdout


def changed_files(checkout):
    text = git(checkout, "status", "--porcelain=v1", "-z", "--untracked-files=all")
    paths = []
    parts = text.split("\0")
    i = 0
    while i < len(parts):
        entry = parts[i]
        if not entry:
            i += 1
            continue
        status, path = entry[:2], entry[3:]
        paths.append(path)
        i += 2 if "R" in status or "C" in status else 1
    return sorted(set(paths))


def generator_env():
    keep = {k: os.environ[k] for k in ("PATH", "HOME", "LANG", "LC_ALL", "TMPDIR") if k in os.environ}
    keep["PYTHONDONTWRITEBYTECODE"] = "1"
    return keep


def run_generator(target, checkout, family, check):
    argv = [*target["command"], "--family", str(Path(family).resolve())] + (["--check"] if check else [])
    try:
        result = subprocess.run(argv, cwd=checkout, capture_output=True, text=True, env=generator_env(), timeout=GENERATOR_TIMEOUT)
    except (OSError, subprocess.TimeoutExpired) as error:
        raise ProposeError(f"{target['name']}: the generator did not run: {error}") from None
    for line in (result.stdout + result.stderr).strip().splitlines()[-20:]:
        print(f"  {target['name']}: {line}")
    return result.returncode


def change_hash(checkout, paths):
    digest = hashlib.sha256()
    for path in paths:
        full = Path(checkout) / path
        digest.update(path.encode("utf-8") + b"\0")
        digest.update(full.read_bytes() if full.is_file() else b"\0deleted")
        digest.update(b"\0")
    return digest.hexdigest()


def body_of(target, family_doc, previous_doc, paths):
    lines = [
        f"The family spec changed and `{' '.join(target['command'])}` in this repository, run with `--family family.json`, writes:",
        "",
        *[f"- `{p}`" + (" (the copy of the spec it was generated from)" if p == target.get("spec_copy") else "") for p in paths],
        "",
    ]
    found = spec.changes(previous_doc, family_doc) if previous_doc else []
    if found:
        lines += ["What changed in the family:", "", *[f"- {c}" for c in found], ""]
    lines += [
        f"Family spec `{family_doc['content_sha256'][:10]}`, registry {family_doc['source']['registry_version']}, from https://github.com/{spec.SELF}/blob/{spec.SPEC_BRANCH}/{spec.SPEC_FILE}.",
        "",
        "Opened by formadaptor. It never pushes to main; merge this when the checks pass, or close it and the next change opens a new one.",
    ]
    return "\n".join(lines) + "\n"


def plan(target, checkout, family, previous=None):
    if git(checkout, "status", "--porcelain").strip():
        raise ProposeError(f"{target['name']}: the checkout is not clean before the generator runs")
    family_doc = spec.load(family)
    if family_doc is None or family_doc.get("content_sha256") != spec.content_hash(family_doc):
        raise ProposeError("the family spec is missing or does not match its own content_sha256")
    code = run_generator(target, checkout, family, check=True)
    if code == 0:
        return None
    if code != 1:
        raise ProposeError(f"{target['name']}: the generator's --check exited {code}, not 0 or 1")
    code = run_generator(target, checkout, family, check=False)
    if code != 0:
        raise ProposeError(f"{target['name']}: the generator exited {code}")
    paths = changed_files(checkout)
    if not paths:
        raise ProposeError(f"{target['name']}: --check reported a difference but the generator changed no file")
    outside = [p for p in paths if not allowed(p, target["files"])]
    if outside:
        raise ProposeError(f"{target['name']}: the generator changed files outside its declared list: {', '.join(outside)}")
    copy = target["spec_copy"]
    if paths == [copy]:
        print(f"::warning::{target['name']}: --check reported a difference but the generator changed only {copy}; nothing a person can see changed, so nothing is proposed")
        return None
    kept = Path(checkout) / copy
    if not kept.is_file() or kept.read_bytes() != Path(family).read_bytes():
        raise ProposeError(f"{target['name']}: the generator changed {', '.join(p for p in paths if p != copy)} but did not leave {copy} a copy of the spec it was given")
    digest = change_hash(checkout, paths)
    previous_doc = spec.load(previous)
    return {
        "target": target["name"],
        "repository": target["repository"],
        "branch": f"{target['branch_prefix']}{digest[:10]}",
        "files": paths,
        "title": spec.title(previous_doc, family_doc),
        "body": body_of(target, family_doc, previous_doc, paths),
    }


def open_bot_pulls(gh, target):
    pulls = gh.paged(f"/repos/{target['repository']}/pulls?state=open&base={BASE}")
    return [p for p in pulls if (p.get("head") or {}).get("ref", "").startswith(target["branch_prefix"])
            and ((p.get("head") or {}).get("repo") or {}).get("full_name", "").lower() == target["repository"].lower()]


def push(checkout, target, proposal, token):
    env = dict(os.environ, GIT_AUTHOR_NAME=IDENTITY[0], GIT_AUTHOR_EMAIL=IDENTITY[1], GIT_COMMITTER_NAME=IDENTITY[0], GIT_COMMITTER_EMAIL=IDENTITY[1])
    git(checkout, "checkout", "-q", "-b", proposal["branch"])
    git(checkout, "add", "-A", "--", *proposal["files"])
    git(checkout, "commit", "-q", "-m", proposal["title"], "-m", proposal["body"], env=env)
    basic = base64.b64encode(f"x-access-token:{token}".encode("utf-8")).decode("ascii")
    base = os.environ.get("FORMADAPTOR_GIT_BASE", "https://github.com").rstrip("/")
    url = f"{base}/{target['repository']}.git"
    git(checkout, "-c", f"http.{base}/.extraheader=AUTHORIZATION: basic {basic}", "push", "-q", url, f"HEAD:refs/heads/{proposal['branch']}")


def propose(gh, checkout, target, proposal, token):
    older = open_bot_pulls(gh, target)
    if any(p["head"]["ref"] == proposal["branch"] for p in older):
        return None, []
    push(checkout, target, proposal, token)
    pull = gh.request("POST", f"/repos/{target['repository']}/pulls", {
        "title": proposal["title"], "head": proposal["branch"], "base": BASE, "body": proposal["body"], "maintainer_can_modify": True,
    })[0]
    closed = []
    for old in older:
        gh.request("POST", f"/repos/{target['repository']}/issues/{old['number']}/comments", {"body": f"Superseded by #{pull['number']}."})
        gh.request("PATCH", f"/repos/{target['repository']}/pulls/{old['number']}", {"state": "closed"})
        try:
            gh.request("DELETE", f"/repos/{target['repository']}/git/refs/heads/{old['head']['ref']}")
        except ApiError as error:
            if error.status not in (404, 422):
                raise
        closed.append(old["number"])
    return pull, closed


def main():
    parser = argparse.ArgumentParser(description="run a target's generator against the family spec and propose the difference")
    sub = parser.add_subparsers(dest="command", required=True)
    sub.add_parser("matrix", help="the enabled targets, as a JSON list for a workflow matrix")
    run = sub.add_parser("run")
    run.add_argument("--target", required=True)
    run.add_argument("--checkout", required=True, help="a clean checkout of the target repository at main")
    run.add_argument("--family", required=True)
    run.add_argument("--previous", help="the spec before this one, for the title")
    run.add_argument("--dry-run", action="store_true", help="say what would be proposed; push and open nothing")
    run.add_argument("--targets", default=str(TARGETS))
    args = parser.parse_args()
    try:
        if args.command == "matrix":
            rows = [{"name": t["name"], "repository": t["repository"], "repo": t["repository"].split("/", 1)[1]} for t in load_targets() if t["enabled"]]
            print(json.dumps(rows, separators=(",", ":")))
            return 0
        target = find(load_targets(args.targets), args.target)
        if not target["enabled"]:
            print(f"{target['name']}: disabled in targets.json, nothing to do")
            output("proposed", "false")
            return 0
        proposal = plan(target, Path(args.checkout), args.family, args.previous)
        if proposal is None:
            summary(f"{target['name']}: in step with the family spec, nothing to propose\n")
            output("proposed", "false")
            return 0
        if args.dry_run:
            print(json.dumps({k: v for k, v in proposal.items() if k != "body"}, indent=2))
            print(proposal["body"])
            output("proposed", "false")
            return 0
        token = os.environ.get("FORMADAPTOR_TARGET_TOKEN", "").strip()
        if not token:
            raise ProposeError("FORMADAPTOR_TARGET_TOKEN is not set")
        pull, closed = propose(GitHub(token=token), Path(args.checkout), target, proposal, token)
        if pull is None:
            summary(f"{target['name']}: {proposal['branch']} is already open, nothing new to propose\n")
            output("proposed", "false")
            return 0
        summary(f"{target['name']}: opened {pull.get('html_url', '#' + str(pull['number']))} from {proposal['branch']}"
                + (f", closed {', '.join('#' + str(n) for n in closed)} as superseded" if closed else "") + "\n")
        output("proposed", "true")
    except (ProposeError, ApiError, ValueError) as error:
        sys.exit(f"::error::{error}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
