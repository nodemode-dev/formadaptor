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
APP_CHECKOUTS = re.compile(r"^\.\./(?!\.{1,2}$)[A-Za-z0-9._-]+$")
APP_REPO = re.compile(r"^[A-Za-z0-9._-]+$")
APP_TAG = re.compile(r"^v\d+\.\d+\.\d+$")
CONTROL = re.compile(r"[\x00-\x1f\x7f-\x9f]")
HEX40 = re.compile(r"^[0-9a-f]{40}$")
HEX64 = re.compile(r"^[0-9a-f]{64}$")
PLAN_FORMAT = "formadaptor-plan"
TITLE_LIMIT = 200
BODY_LIMIT = 60000
BASE = "main"
IDENTITY = ("nodemode-ai", "mackin@nodemode.ai")
GENERATOR_TIMEOUT = 600
FETCH_TIMEOUT = 600
LISTED = 50


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
        if "app_checkouts" in target and not (isinstance(target["app_checkouts"], str) and APP_CHECKOUTS.match(target["app_checkouts"])):
            problems.append("app_checkouts must be one folder beside the checkout, ../<name>")
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


def listed_paths(target, paths):
    if len(paths) <= LISTED:
        return paths
    copy = [p for p in paths if p == target.get("spec_copy")]
    return copy + [p for p in paths if p not in copy][:LISTED - len(copy)]


def fetch_apps(target, checkout, family_doc):
    if "app_checkouts" not in target:
        return None
    root = (Path(checkout).resolve() / target["app_checkouts"]).resolve()
    if root.exists() and any(root.iterdir()):
        raise ProposeError(f"{target['name']}: {root} is not empty; the app checkouts are only ever made in a new folder")
    base = os.environ.get("FORMADAPTOR_GIT_BASE", "https://github.com").rstrip("/")
    env = dict(generator_env(), GIT_TERMINAL_PROMPT="0", GIT_LFS_SKIP_SMUDGE="1")
    fetched = []
    for app in public_apps(family_doc) or []:
        release = app.get("release")
        if not isinstance(release, dict):
            continue
        repo, repository, tag = app.get("repo", ""), app.get("repository", ""), release.get("tag", "")
        if not (isinstance(repo, str) and APP_REPO.match(repo) and repo not in (".", "..") and repository == f"nodemode-dev/{repo}"
                and isinstance(tag, str) and APP_TAG.match(tag)):
            raise ProposeError(f"{target['name']}: app {app.get('id', '?')} has no plain repository and released tag in the spec")
        root.mkdir(parents=True, exist_ok=True)
        argv = ["git", "-c", "core.hooksPath=/dev/null", "-c", "advice.detachedHead=false", "clone", "-q", "--depth", "1",
                "--single-branch", "--no-tags", "--branch", tag, "--", f"{base}/{repository}.git", str(root / repo)]
        try:
            result = subprocess.run(argv, capture_output=True, text=True, env=env, timeout=FETCH_TIMEOUT)
        except (OSError, subprocess.TimeoutExpired) as error:
            raise ProposeError(f"{target['name']}: {repository} at {tag} was not fetched: {error}") from None
        if result.returncode != 0:
            raise ProposeError(f"{target['name']}: {repository} at {tag} was not fetched: {result.stderr.strip()[:300]}")
        print(f"  {target['name']}: {repo} at {tag}")
        fetched.append(repo)
    return fetched


def body_of(target, family_doc, previous_doc, paths):
    lines = [
        f"The family spec changed and `{' '.join(target['command'])}` in this repository, run with `--family family.json`, writes:",
        "",
        *[f"- `{p}`" + (" (the copy of the spec it was generated from)" if p == target.get("spec_copy") else "") for p in listed_paths(target, paths)],
        *([f"- and {len(paths) - LISTED} more files"] if len(paths) > LISTED else []),
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


def public_apps(doc):
    apps = doc.get("apps") if isinstance(doc, dict) else None
    if not isinstance(apps, list):
        return None
    return [a for a in apps if isinstance(a, dict) and a.get("public") is True]


def kept_spec(checkout, target):
    try:
        return spec.load(Path(checkout) / target["spec_copy"])
    except (OSError, ValueError):
        return None


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
    shown_before = public_apps(kept_spec(checkout, target))
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
    warning = None
    if shown_before is not None and shown_before == public_apps(family_doc):
        warning = (f"{target['name']}: {', '.join(p for p in paths if p != copy)} differs although this spec and the one it was generated from hold the same public app data; "
                   "its generator is recording something that is not app data (docs/TARGETS.md)")
    return {
        "warning": warning,
        "target": target["name"],
        "repository": target["repository"],
        "branch": f"{target['branch_prefix']}{digest[:10]}",
        "change_hash": digest,
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


def sha256_of(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def head(checkout):
    return git(checkout, "rev-parse", "--verify", "HEAD^{commit}").strip()


def plain_path(path, files):
    return (isinstance(path, str) and 0 < len(path) <= 1024 and not path.startswith("/") and "\\" not in path and not CONTROL.search(path)
            and all(part not in ("", ".", "..") for part in path.split("/")) and allowed(path, files))


def write_plan(target, checkout, proposal, base, out):
    out = Path(out)
    if out.is_symlink() or (out.exists() and (not out.is_dir() or any(out.iterdir()))):
        raise ProposeError(f"{target['name']}: {out} is not a new, empty folder for the plan")
    entries = []
    for path in proposal["files"]:
        source = Path(checkout) / path
        if not inside(checkout, path):
            raise ProposeError(f"{target['name']}: the generator left {path!r} as a link; only plain files are proposed")
        if source.is_file():
            copy = out / "files" / path
            copy.parent.mkdir(parents=True, exist_ok=True)
            copy.write_bytes(source.read_bytes())
            entries.append({"path": path, "sha256": sha256_of(copy)})
        elif source.exists():
            raise ProposeError(f"{target['name']}: {path!r} is not a plain file")
        else:
            entries.append({"path": path, "deleted": True})
    doc = {
        "format": PLAN_FORMAT, "format_version": 1, "target": target["name"], "repository": target["repository"], "base": base,
        "branch": proposal["branch"], "change_hash": proposal["change_hash"], "paths": proposal["files"],
        "title": proposal["title"], "body": proposal["body"], "warning": proposal["warning"], "files": entries,
    }
    out.mkdir(parents=True, exist_ok=True)
    (out / "proposal.json").write_text(json.dumps(doc, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    return doc


def read_plan_doc(plandir):
    plandir = Path(plandir)
    if plandir.is_symlink() or not plandir.is_dir():
        raise ProposeError(f"{str(plandir)!r} is not a plan folder")
    doc_path = plandir / "proposal.json"
    if doc_path.is_symlink() or not doc_path.is_file():
        raise ProposeError(f"{str(plandir)!r} holds no plain proposal.json")
    try:
        doc = json.loads(doc_path.read_text(encoding="utf-8"))
    except (OSError, UnicodeDecodeError, json.JSONDecodeError) as error:
        raise ProposeError(f"proposal.json does not load: {str(error)[:200]!r}") from None
    if not isinstance(doc, dict) or doc.get("format") != PLAN_FORMAT or doc.get("format_version") != 1:
        raise ProposeError(f"proposal.json is not a {PLAN_FORMAT} version 1 file")
    return doc


def checked_plan(target, plandir):
    plandir = Path(plandir)
    doc = read_plan_doc(plandir)
    name = target["name"]
    if doc.get("target") != name:
        raise ProposeError(f"{name}: the plan names the target {str(doc.get('target'))[:60]!r}")
    if doc.get("repository") != target["repository"]:
        raise ProposeError(f"{name}: the plan names the repository {str(doc.get('repository'))[:100]!r}, not {target['repository']}")
    base, digest, branch = doc.get("base"), doc.get("change_hash"), doc.get("branch")
    if not (isinstance(base, str) and HEX40.match(base)):
        raise ProposeError(f"{name}: the plan's base is not a commit sha")
    if not (isinstance(digest, str) and HEX64.match(digest)):
        raise ProposeError(f"{name}: the plan's change hash is not a sha256")
    if not (isinstance(branch, str) and branch.startswith(target["branch_prefix"]) and branch == f"{target['branch_prefix']}{digest[:10]}"):
        raise ProposeError(f"{name}: the plan's branch {str(branch)[:100]!r} is not {target['branch_prefix']} and its change hash")
    title, body, warning = doc.get("title"), doc.get("body"), doc.get("warning")
    if not isinstance(title, str) or not title.strip() or not isinstance(body, str) or not (warning is None or isinstance(warning, str)):
        raise ProposeError(f"{name}: the plan's title, body or warning is not text")
    paths, entries = doc.get("paths"), doc.get("files")
    if not isinstance(paths, list) or not paths or not isinstance(entries, list) or len(entries) != len(paths):
        raise ProposeError(f"{name}: the plan lists no files, or its paths and files differ")
    copied, deleted = {}, set()
    for entry in entries:
        path = entry.get("path") if isinstance(entry, dict) else None
        if not plain_path(path, target["files"]):
            raise ProposeError(f"{name}: the plan names {str(path)[:200]!r}, which is not one of the target's files")
        if path in copied or path in deleted:
            raise ProposeError(f"{name}: the plan names {path!r} twice")
        if set(entry) == {"path", "deleted"} and entry["deleted"] is True:
            deleted.add(path)
        elif set(entry) == {"path", "sha256"} and isinstance(entry["sha256"], str) and HEX64.match(entry["sha256"]):
            copied[path] = entry["sha256"]
        else:
            raise ProposeError(f"{name}: the plan's entry for {path!r} is neither a copied file with its sha256 nor a deletion")
    if paths != sorted(set(copied) | deleted) or not all(isinstance(p, str) for p in paths):
        raise ProposeError(f"{name}: the plan's paths are not exactly its files, in order")
    root = plandir / "files"
    found = set()
    if root.is_symlink() or (root.exists() and not root.is_dir()):
        raise ProposeError(f"{name}: the plan's files folder is a link or not a folder")
    for folder, dirs, names in os.walk(root, followlinks=False):
        for entry in dirs + names:
            full = Path(folder) / entry
            rel = full.relative_to(root).as_posix()
            if full.is_symlink():
                raise ProposeError(f"{name}: the plan holds a link, {rel[:200]!r}")
            if full.is_dir():
                continue
            if not full.is_file() or rel not in copied:
                raise ProposeError(f"{name}: the plan holds {rel[:200]!r}, which it does not list as a copied file")
            if sha256_of(full) != copied[rel]:
                raise ProposeError(f"{name}: {rel!r} in the plan does not match its listed sha256")
            found.add(rel)
    if found != set(copied):
        raise ProposeError(f"{name}: the plan lists {', '.join(sorted(set(copied) - found))[:300]!r} but does not hold them")
    return {
        "base": base,
        "plandir": plandir,
        "deleted": sorted(deleted),
        "proposal": {"warning": warning, "target": name, "repository": target["repository"], "branch": branch, "change_hash": digest,
                     "files": paths, "title": title[:TITLE_LIMIT], "body": body[:BODY_LIMIT]},
    }


def inside(checkout, path):
    root = Path(checkout).resolve()
    current = root
    for part in path.split("/"):
        current = current / part
        if current.is_symlink():
            return False
    return root in (root / path).resolve().parents


def apply_plan(target, checkout, checked):
    checkout = Path(checkout)
    for path in checked["proposal"]["files"]:
        if not inside(checkout, path):
            raise ProposeError(f"{target['name']}: {path!r} would be written through a link in the checkout")
    for path in checked["proposal"]["files"]:
        full = checkout / path
        if path in checked["deleted"]:
            if full.is_file():
                full.unlink()
            elif full.exists():
                raise ProposeError(f"{target['name']}: {path!r} is not a plain file in the checkout")
        else:
            if full.exists() and not full.is_file():
                raise ProposeError(f"{target['name']}: {path!r} is not a plain file in the checkout")
            full.parent.mkdir(parents=True, exist_ok=True)
            full.write_bytes((checked["plandir"] / "files" / path).read_bytes())


def changed_plans(plans, targets):
    enabled = {t["name"]: t for t in targets if t["enabled"]}
    rows = []
    root = Path(plans)
    if not root.is_dir():
        return rows
    for folder in sorted(root.iterdir()):
        label = repr(folder.name[:80])
        if folder.is_symlink() or not folder.is_dir() or not folder.name.startswith("plan-"):
            print(f"::warning::{label} is not a plan folder, skipped", file=sys.stderr)
            continue
        name = folder.name[len("plan-"):]
        if name not in enabled:
            print(f"::warning::{label} names no enabled target, skipped", file=sys.stderr)
            continue
        try:
            doc = read_plan_doc(folder)
        except ProposeError as error:
            print(f"::warning::{label}: {error}, skipped", file=sys.stderr)
            continue
        if doc.get("target") != name:
            print(f"::warning::{label}: its proposal.json names another target, skipped", file=sys.stderr)
            continue
        target = enabled[name]
        rows.append({"name": name, "repository": target["repository"], "repo": target["repository"].split("/", 1)[1]})
    return rows


def plan_command(target, args):
    if not target["enabled"]:
        print(f"{target['name']}: disabled in targets.json, nothing to do")
        output("changed", "false")
        return 0
    checkout = Path(args.checkout)
    base = head(checkout)
    proposal = plan(target, checkout, args.family, args.previous)
    if proposal is None:
        summary(f"{target['name']}: in step with the family spec, nothing to propose\n")
        output("changed", "false")
        return 0
    if head(checkout) != base:
        raise ProposeError(f"{target['name']}: the generator moved the checkout's HEAD")
    if proposal["warning"]:
        print(f"::warning::{proposal['warning']}")
        summary(f"Warning: {proposal['warning']}. The proposal is not held back.\n")
    doc = write_plan(target, checkout, proposal, base, args.out)
    print(f"{target['name']}: planned {proposal['branch']} on {base[:10]}, {len(doc['files'])} files")
    output("changed", "true")
    return 0


def apply_command(target, args):
    if not target["enabled"]:
        print(f"{target['name']}: disabled in targets.json, nothing to do")
        output("proposed", "false")
        return 0
    token = os.environ.get("FORMADAPTOR_TARGET_TOKEN", "").strip()
    if not token:
        raise ProposeError("FORMADAPTOR_TARGET_TOKEN is not set")
    checked = checked_plan(target, args.plan)
    proposal = checked["proposal"]
    checkout = Path(args.checkout)
    if head(checkout) != checked["base"]:
        summary(f"{target['name']}: main moved since the plan was made on {checked['base'][:10]}; nothing is pushed, the next run proposes again\n")
        output("proposed", "false")
        return 0
    if git(checkout, "status", "--porcelain").strip():
        raise ProposeError(f"{target['name']}: the checkout is not clean before the plan is applied")
    apply_plan(target, checkout, checked)
    if changed_files(checkout) != proposal["files"] or change_hash(checkout, proposal["files"]) != proposal["change_hash"]:
        raise ProposeError(f"{target['name']}: the applied files do not give the plan's change hash")
    if proposal["warning"]:
        summary(f"Warning: {CONTROL.sub(' ', proposal['warning'])[:1000]}. The proposal is not held back.\n")
    pull, closed = propose(GitHub(token=token), checkout, target, proposal, token)
    if pull is None:
        summary(f"{target['name']}: {proposal['branch']} is already open, nothing new to propose\n")
        output("proposed", "false")
        return 0
    summary(f"{target['name']}: opened {pull.get('html_url', '#' + str(pull['number']))} from {proposal['branch']}"
            + (f", closed {', '.join('#' + str(n) for n in closed)} as superseded" if closed else "") + "\n")
    output("proposed", "true")
    return 0


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
    apps = sub.add_parser("checkouts", help="fetch each public released app at its tag where the target's generator reads them")
    apps.add_argument("--target", required=True)
    apps.add_argument("--checkout", required=True, help="the checkout of the target repository the generator will run in")
    apps.add_argument("--family", required=True)
    apps.add_argument("--targets", default=str(TARGETS))
    planned = sub.add_parser("plan", help="run the target's generator and write what it would propose into a plan folder; no token")
    planned.add_argument("--target", required=True)
    planned.add_argument("--checkout", required=True, help="a clean checkout of the target repository at main")
    planned.add_argument("--family", required=True)
    planned.add_argument("--previous", help="the spec before this one, for the title")
    planned.add_argument("--out", required=True, help="a new folder for proposal.json and files/")
    planned.add_argument("--targets", default=str(TARGETS))
    found = sub.add_parser("changed", help="the enabled targets that have a plan, as a JSON list for a workflow matrix")
    found.add_argument("--plans", required=True, help="one plan-<target> folder per plan")
    found.add_argument("--targets", default=str(TARGETS))
    applied = sub.add_parser("apply", help="check a plan, copy its files into the checkout and propose them; runs no target code")
    applied.add_argument("--target", required=True)
    applied.add_argument("--checkout", required=True, help="a clean checkout of the target repository at main")
    applied.add_argument("--plan", required=True)
    applied.add_argument("--targets", default=str(TARGETS))
    args = parser.parse_args()
    try:
        if args.command == "matrix":
            rows = [{"name": t["name"], "repository": t["repository"], "repo": t["repository"].split("/", 1)[1]} for t in load_targets() if t["enabled"]]
            print(json.dumps(rows, separators=(",", ":")))
            return 0
        if args.command == "checkouts":
            target = find(load_targets(args.targets), args.target)
            if not target["enabled"] or "app_checkouts" not in target:
                print(f"{target['name']}: needs no app checkouts")
                return 0
            family_doc = spec.load(args.family)
            if family_doc is None or family_doc.get("content_sha256") != spec.content_hash(family_doc):
                raise ProposeError("the family spec is missing or does not match its own content_sha256")
            fetched = fetch_apps(target, Path(args.checkout), family_doc)
            print(f"{target['name']}: {len(fetched)} public apps at their released tags in {target['app_checkouts']}")
            return 0
        if args.command == "changed":
            print(json.dumps(changed_plans(args.plans, load_targets(args.targets)), separators=(",", ":")))
            return 0
        target = find(load_targets(args.targets), args.target)
        if args.command == "plan":
            return plan_command(target, args)
        if args.command == "apply":
            return apply_command(target, args)
        if not target["enabled"]:
            print(f"{target['name']}: disabled in targets.json, nothing to do")
            output("proposed", "false")
            return 0
        proposal = plan(target, Path(args.checkout), args.family, args.previous)
        if proposal is None:
            summary(f"{target['name']}: in step with the family spec, nothing to propose\n")
            output("proposed", "false")
            return 0
        if proposal["warning"]:
            print(f"::warning::{proposal['warning']}")
            summary(f"Warning: {proposal['warning']}. The proposal is not held back.\n")
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
