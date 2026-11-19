import argparse
import json
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
IDS = ROOT / "spec" / "ids.json"
REPOSITORY = re.compile(r"^nodemode-dev/([A-Za-z0-9._-]+)$")
NEEDED = ("app", "repository", "enabled", "catalog")
CATALOG_NEEDED = ("id", "name", "kind", "summary", "licence", "state")


class RegistryError(Exception):
    pass


def load(compiler):
    apps_dir = Path(compiler) / "apps"
    if not apps_dir.is_dir():
        raise RegistryError(f"{apps_dir} is not formcompiler's registry folder")
    entries = []
    for path in sorted(apps_dir.glob("*.json")):
        entry = json.loads(path.read_text(encoding="utf-8"))
        missing = [k for k in NEEDED if k not in entry] + [f"catalog.{k}" for k in CATALOG_NEEDED if k not in entry.get("catalog", {})]
        if missing:
            raise RegistryError(f"{path.name}: missing {', '.join(missing)}")
        if entry["app"] != path.stem:
            raise RegistryError(f"{path.name}: app {entry['app']!r} does not match the file name")
        if not REPOSITORY.match(entry["repository"]):
            raise RegistryError(f"{path.name}: repository {entry['repository']!r} is not nodemode-dev/<repo>")
        entries.append(entry)
    if not entries:
        raise RegistryError(f"{apps_dir} holds no registry files")
    return entries


def version(compiler):
    path = Path(compiler) / "VERSION"
    return path.read_text(encoding="utf-8").strip() if path.is_file() else ""


def repo_of(entry):
    return REPOSITORY.match(entry["repository"]).group(1)


def ids(entries):
    rows = [{"app": e["app"], "repo": repo_of(e), "catalog": e["catalog"]["id"], "site": e["catalog"]["id"]} for e in entries]
    return {"format": "formadaptor-ids", "format_version": 1, "apps": sorted(rows, key=lambda r: r["app"])}


def load_ids(path=IDS):
    data = json.loads(Path(path).read_text(encoding="utf-8"))
    return {row["app"]: row for row in data["apps"]}


def id_problems(entries, path=IDS):
    want = {row["app"]: row for row in ids(entries)["apps"]}
    have = load_ids(path)
    problems = []
    for app in sorted(set(want) | set(have)):
        if app not in have:
            problems.append(f"{app}: in the registry, not in spec/ids.json")
        elif app not in want:
            problems.append(f"{app}: in spec/ids.json, not in the registry")
        else:
            for key in ("repo", "catalog"):
                if want[app][key] != have[app][key]:
                    problems.append(f"{app}: {key} is {want[app][key]!r} in the registry, {have[app][key]!r} in spec/ids.json")
    seen = {}
    for row in have.values():
        for key in ("catalog", "site"):
            other = seen.setdefault((key, row[key]), row["app"])
            if other != row["app"]:
                problems.append(f"{key} id {row[key]!r} is used by both {other} and {row['app']}")
    return problems


def main():
    parser = argparse.ArgumentParser(description="formcompiler's registry as formadaptor reads it")
    parser.add_argument("command", choices=["ids", "list"])
    parser.add_argument("--compiler", required=True, help="a checkout of nodemode-dev/formcompiler")
    parser.add_argument("--check", action="store_true", help="ids: fail when spec/ids.json differs from the registry")
    args = parser.parse_args()
    try:
        entries = load(args.compiler)
    except (RegistryError, ValueError) as error:
        sys.exit(f"registry: {error}")
    if args.command == "list":
        print(json.dumps([{"app": e["app"], "repo": repo_of(e), "enabled": e["enabled"]} for e in entries], indent=2))
        return 0
    if not args.check:
        print(json.dumps(ids(entries), indent=2))
        return 0
    problems = id_problems(entries)
    for problem in problems:
        print(f"::error::{problem}")
    print(f"ids: {len(entries)} registry entries, {'in step' if not problems else f'{len(problems)} problems'}")
    return 1 if problems else 0


if __name__ == "__main__":
    sys.exit(main())
