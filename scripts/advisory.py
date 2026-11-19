import argparse
import json
import sys
import urllib.parse
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import manifest
from github_api import ORG, ApiError, GitHub, summary

MAIN = "main"
LISTS = (("mcp", "tools", "tools"), ("mcp", "read_only", "read-only tools"), ("mcp", "approval_gated", "approval-gated tools"),
         ("mcp", "transports", "transports"), ("dock", "positions", "dock positions"), ("dock", "tabs", "dock tabs"))


def parsed(text):
    if text is None:
        return None, ""
    try:
        doc = json.loads(text)
    except ValueError:
        return None, "is not valid JSON"
    return doc, ""


def moved(label, old, new):
    found = []
    added = [n for n in new if n not in old]
    removed = [n for n in old if n not in new]
    if added:
        found.append(f"adds {label} {', '.join(added)}")
    if removed:
        found.append(f"drops {label} {', '.join(removed)}")
    return found


def part(doc, section, key):
    block = doc.get(section) if isinstance(doc, dict) else None
    value = block.get(key) if isinstance(block, dict) else None
    return [str(v) for v in value] if isinstance(value, list) else []


def skills_of(doc):
    rows = doc.get("skills") if isinstance(doc, dict) else None
    return {str(s.get("name")): [str(x) for x in s.get("sub_skills") or []] for s in rows or [] if isinstance(s, dict)}


def manifest_differences(old, new):
    found = []
    if (old.get("mcp") is None) != (new.get("mcp") is None):
        found.append("adds an MCP server" if old.get("mcp") is None else "drops its MCP server")
    for section, key, label in LISTS:
        found += moved(label, part(old, section, key), part(new, section, key))
    before, after = skills_of(old), skills_of(new)
    found += moved("skills", list(before), list(after))
    for name in after:
        if name in before:
            found += moved(f"sub-skills of {name}:", before[name], after[name])
    if (old.get("dock") or {}).get("present") != (new.get("dock") or {}).get("present"):
        found.append("adds the dock" if (new.get("dock") or {}).get("present") else "drops the dock")
    if old.get("extensions") != new.get("extensions"):
        found.append(f"extensions {json.dumps(old.get('extensions'))} becomes {json.dumps(new.get('extensions'))}")
    if not found and old != new:
        found.append("changes agents/manifest.json in other fields")
    return found


def compare_manifests(gh, repository, tag):
    released_text = gh.file_at(repository, manifest.PATH, tag)
    main_text = gh.file_at(repository, manifest.PATH, MAIN)
    if released_text == main_text:
        return []
    if released_text is None:
        return ["adds agents/manifest.json"]
    if main_text is None:
        return ["drops agents/manifest.json"]
    released, bad_released = parsed(released_text)
    current, bad_main = parsed(main_text)
    if bad_main:
        return [f"agents/manifest.json on {MAIN} {bad_main}"]
    if bad_released:
        return [f"agents/manifest.json at {tag} {bad_released}; {MAIN} has one that parses"]
    return manifest_differences(released, current)


def skill_folders(gh, repository, ref, root):
    tree = gh.get(f"/repos/{repository}/git/trees/{urllib.parse.quote(ref)}?recursive=1")
    if tree.get("truncated"):
        raise ValueError(f"the tree of {repository} at {ref} is too large to list in one answer")
    prefix = root.strip("/") + "/"
    found = set()
    for item in tree.get("tree") or []:
        path = str(item.get("path") or "")
        if item.get("type") == "blob" and path.startswith(prefix):
            rest = path[len(prefix):].split("/")
            if len(rest) == 2 and rest[1] == "SKILL.md" and not rest[0].startswith("."):
                found.add(rest[0])
    return sorted(found)


def compare_skills(gh, repository, tag, root):
    if not root:
        return []
    return moved("skill folders", skill_folders(gh, repository, tag, root), skill_folders(gh, repository, MAIN, root))


def check(gh, family):
    report = []
    for app in family.get("apps") or []:
        if not app.get("public") or not app.get("release"):
            continue
        tag = app["release"]["tag"]
        repository = app.get("repository") or f"{ORG}/{app['repo']}"
        name = app.get("name") or app["id"]
        try:
            found = compare_manifests(gh, repository, tag) + compare_skills(gh, repository, tag, (app.get("agents") or {}).get("skills") or "")
        except (ApiError, ValueError) as error:
            report.append((name, tag, [f"could not be compared: {error}"]))
            continue
        if found:
            report.append((name, tag, found))
    return report


def main():
    parser = argparse.ArgumentParser(description="advisory: has main changed what each public app offers agents since its release? never fails")
    parser.add_argument("--family", required=True, help="the family.json just built")
    args = parser.parse_args()
    try:
        family = json.loads(Path(args.family).read_text(encoding="utf-8"))
        report = check(GitHub(), family)
    except (OSError, ValueError, ApiError) as error:
        print(f"::warning::advisory check against {MAIN} did not run: {error}")
        return 0
    summary(f"\n### {MAIN} against the released tag (advisory)\n\n")
    if not report:
        summary(f"Every public app's {MAIN} offers agents what its newest release does.\n")
        return 0
    for name, tag, found in report:
        summary(f"- {name} ({MAIN} against {tag}): {'; '.join(found)}\n")
    summary(f"\nNothing is proposed for these; they say {MAIN} has changed what it offers agents since the last release.\n")
    return 0


if __name__ == "__main__":
    sys.exit(main())
