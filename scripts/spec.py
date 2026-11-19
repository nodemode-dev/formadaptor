import argparse
import base64
import datetime
import hashlib
import json
import os
import sys
import urllib.parse
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import manifest
import registry
import releases
import visibility
from github_api import ApiError, GitHub, output, summary

FORMAT = "formai-family"
FORMAT_VERSION = 1
SPEC_BRANCH = "spec"
SPEC_FILE = "family.json"
SELF = "nodemode-dev/formadaptor"


def canonical(doc):
    body = {k: v for k, v in doc.items() if k not in ("generated", "content_sha256")}
    return json.dumps(body, sort_keys=True, separators=(",", ":"), ensure_ascii=False)


def content_hash(doc):
    return hashlib.sha256(canonical(doc).encode("utf-8")).hexdigest()


def now_utc():
    return datetime.datetime.now(datetime.timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def public_app(gh, entry, row, yanked):
    catalog = entry["catalog"]
    agents = entry.get("agents") or {}
    repo = row["repo"]
    app = {
        "id": catalog["id"],
        "public": True,
        "app": entry["app"],
        "repo": repo,
        "repository": entry["repository"],
        "site": row["site"],
        "name": catalog["name"],
        "kind": catalog["kind"],
        "summary": catalog["summary"],
        "licence": catalog["licence"],
        "state": catalog["state"],
        "launcher": (entry.get("build") or {}).get("cli") or entry["app"],
        "agents": {"mcp": bool(agents.get("mcp")), "skills": agents.get("skills") or ""},
        "release": releases.latest(gh, repo, entry["app"], yanked),
    }
    if app["release"]:
        counts = manifest.read(gh, repo, app["release"]["tag"], entry["app"])
        if counts is not None:
            app["manifest"] = counts
    return app


def build(compiler, gh, generated=None, ids_path=registry.IDS):
    entries = registry.load(compiler)
    problems = registry.id_problems(entries, ids_path)
    if problems:
        raise registry.RegistryError("spec/ids.json is not in step with the registry: " + "; ".join(problems))
    ids = registry.load_ids(ids_path)
    yanked = releases.load_yanked(compiler)
    apps = []
    for entry in sorted((e for e in entries if e["enabled"]), key=lambda e: e["catalog"]["id"]):
        row = ids[entry["app"]]
        if visibility.public(gh, row["repo"]):
            apps.append(public_app(gh, entry, row, yanked))
        else:
            apps.append({"id": entry["catalog"]["id"], "public": False})
    doc = {
        "format": FORMAT,
        "format_version": FORMAT_VERSION,
        "generated": generated or now_utc(),
        "source": {"repository": "nodemode-dev/formcompiler", "registry_version": registry.version(compiler)},
        "content_sha256": "",
        "apps": apps,
    }
    doc["content_sha256"] = content_hash(doc)
    return doc


def text_of(doc):
    return json.dumps(doc, indent=2, ensure_ascii=False) + "\n"


def load(path):
    if not path or not Path(path).is_file():
        return None
    return json.loads(Path(path).read_text(encoding="utf-8"))


def changes(old, new):
    if not old:
        return []
    before = {a["id"]: a for a in old.get("apps", [])}
    after = {a["id"]: a for a in new.get("apps", [])}
    found = []
    for app_id, app in after.items():
        was = before.get(app_id)
        name = app.get("name") or app_id
        if not app["public"]:
            if was and was["public"]:
                found.append(f"{app_id} is no longer public")
            continue
        if was is None:
            found.append(f"{name} joins the family")
            continue
        if not was["public"]:
            found.append(f"{name} is public")
            continue
        new_version = (app.get("release") or {}).get("version")
        if new_version != (was.get("release") or {}).get("version"):
            found.append(f"{name} {new_version}" if new_version else f"{name} has no release")
        elif app.get("manifest") != was.get("manifest"):
            found.append(f"{name} agent counts")
        elif app != was:
            found.append(f"{name} details")
    for app_id in before:
        if app_id not in after:
            found.append(f"{app_id} leaves the family")
    if old and not found and old.get("source") != new.get("source"):
        found.append(f"registry {new['source']['registry_version']}")
    return found


def title(old, new, limit=3):
    found = changes(old, new)
    if not found:
        return "chore(family): follow the family spec"
    shown = ", ".join(found[:limit])
    more = len(found) - limit
    return f"chore(family): {shown}" + (f" and {more} more" if more > 0 else "")


def fetch(gh, repo, branch, out, previous_out=None):
    try:
        ref = gh.get(f"/repos/{repo}/git/ref/heads/{urllib.parse.quote(branch)}")
    except ApiError as error:
        if error.status == 404:
            return ""
        raise
    sha = ref["object"]["sha"]
    text = gh.file_at(repo, SPEC_FILE, sha)
    if text is None:
        return ""
    Path(out).write_text(text, encoding="utf-8")
    if previous_out:
        parents = gh.get(f"/repos/{repo}/git/commits/{sha}").get("parents") or []
        if parents:
            before = gh.file_at(repo, SPEC_FILE, parents[0]["sha"])
            if before is not None:
                Path(previous_out).write_text(before, encoding="utf-8")
    return sha


def publish(gh, repo, branch, text, doc):
    parent = ""
    try:
        parent = gh.get(f"/repos/{repo}/git/ref/heads/{urllib.parse.quote(branch)}")["object"]["sha"]
    except ApiError as error:
        if error.status != 404:
            raise
    encoded = base64.b64encode(text.encode("utf-8")).decode("ascii")
    blob = gh.request("POST", f"/repos/{repo}/git/blobs", {"content": encoded, "encoding": "base64"})[0]["sha"]
    tree = gh.request("POST", f"/repos/{repo}/git/trees", {"tree": [{"path": SPEC_FILE, "mode": "100644", "type": "blob", "sha": blob}]})[0]["sha"]
    message = f"chore(spec): family.json {doc['content_sha256'][:10]}\n\nRegistry {doc['source']['registry_version']}, built {doc['generated']}."
    commit = gh.request("POST", f"/repos/{repo}/git/commits", {"message": message, "tree": tree, "parents": [parent] if parent else []})[0]["sha"]
    if parent:
        gh.request("PATCH", f"/repos/{repo}/git/refs/heads/{urllib.parse.quote(branch)}", {"sha": commit, "force": True})
    else:
        gh.request("POST", f"/repos/{repo}/git/refs", {"ref": f"refs/heads/{branch}", "sha": commit})
    return commit


def main():
    parser = argparse.ArgumentParser(description="the family spec, family.json")
    sub = parser.add_subparsers(dest="command", required=True)
    make = sub.add_parser("build", help="build family.json from formcompiler's registry and GitHub")
    make.add_argument("--compiler", required=True, help="a checkout of nodemode-dev/formcompiler")
    make.add_argument("--out", default=SPEC_FILE)
    make.add_argument("--previous", help="the published family.json, to say whether anything changed")
    got = sub.add_parser("fetch", help="the published family.json from the spec branch")
    got.add_argument("--out", required=True)
    got.add_argument("--previous-out", help="also the one before it, for pull request titles")
    pub = sub.add_parser("publish", help="put family.json on the spec branch")
    pub.add_argument("--file", required=True)
    shown = sub.add_parser("title", help="the pull request title for a change from one spec to another")
    shown.add_argument("--previous")
    shown.add_argument("--file", required=True)
    args = parser.parse_args()
    repo = os.environ.get("FORMADAPTOR_REPOSITORY", SELF)
    try:
        if args.command == "build":
            doc = build(args.compiler, GitHub())
            Path(args.out).write_text(text_of(doc), encoding="utf-8")
            old = load(args.previous)
            changed = not old or old.get("content_sha256") != doc["content_sha256"]
            public = sum(1 for a in doc["apps"] if a["public"])
            output("changed", "true" if changed else "false")
            output("hash", doc["content_sha256"])
            summary(f"family.json: {len(doc['apps'])} apps, {public} public, {len(doc['apps']) - public} private, "
                    f"{doc['content_sha256'][:10]}, {'changed' if changed else 'unchanged'}\n")
            for line in changes(old, doc) if old else []:
                summary(f"- {line}\n")
        elif args.command == "fetch":
            sha = fetch(GitHub(), repo, SPEC_BRANCH, args.out, args.previous_out)
            output("published", "true" if sha else "false")
            print(f"spec: {'published at ' + sha[:10] if sha else 'nothing published yet'}")
        elif args.command == "publish":
            text = Path(args.file).read_text(encoding="utf-8")
            doc = json.loads(text)
            if doc.get("content_sha256") != content_hash(doc):
                sys.exit("::error::family.json does not match its own content_sha256")
            commit = publish(GitHub(), repo, SPEC_BRANCH, text, doc)
            summary(f"published family.json {doc['content_sha256'][:10]} as {commit[:10]} on {SPEC_BRANCH}\n")
        else:
            print(title(load(args.previous), load(args.file)))
    except (ApiError, registry.RegistryError, ValueError) as error:
        sys.exit(f"::error::{error}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
