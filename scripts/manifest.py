import argparse
import json
import re
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from github_api import ORG, ApiError

PATH = "agents/manifest.json"
FORMAT = "form-agent-manifest"
VERSION = 1
NAME = re.compile(r"^[A-Za-z0-9][A-Za-z0-9._-]{0,79}$")
HOST_API = re.compile(r"^(0|[1-9][0-9]*)(\.(0|[1-9][0-9]*)){0,2}$")
TRANSPORTS = {"stdio", "http"}
POSITIONS = {"left", "right", "bottom", "floating"}
TOP = {"format", "version", "app", "mcp", "skills", "dock", "extensions"}


def names(value, where, problems):
    if not isinstance(value, list) or not all(isinstance(v, str) and NAME.match(v) for v in value):
        problems.append(f"{where} must be a list of names")
        return []
    if len(set(value)) != len(value):
        problems.append(f"{where} lists a name twice")
    return value


def exact(value, keys, where, problems, optional=frozenset()):
    if not isinstance(value, dict):
        problems.append(f"{where} must be an object")
        return False
    for k in sorted(set(value) - keys - optional):
        problems.append(f"{where}.{k} is not a manifest field")
    for k in sorted(keys - set(value)):
        problems.append(f"{where}.{k} is missing")
    return keys <= set(value)


def dispatch_problems(dispatch, tools, problems):
    if not isinstance(dispatch, list) or not dispatch:
        problems.append("mcp.dispatch must be a non-empty list, or left out")
        return
    seen = set()
    for i, row in enumerate(dispatch):
        where = f"mcp.dispatch[{i}]"
        if not exact(row, {"tool", "reaches"}, where, problems):
            continue
        tool, reaches = row["tool"], row["reaches"]
        if not isinstance(tool, str) or not NAME.match(tool):
            problems.append(f"{where}.tool must be a name")
        elif tool not in tools:
            problems.append(f"{where}.tool names {tool!r}, which is not in mcp.tools")
        elif tool in seen:
            problems.append(f"{where}.tool {tool!r} is listed twice")
        else:
            seen.add(tool)
        if not isinstance(reaches, int) or isinstance(reaches, bool) or reaches < 1:
            problems.append(f"{where}.reaches must be a whole number of at least 1")


def problems_of(doc, app=None):
    problems = []
    if not exact(doc, TOP, "manifest", problems):
        return problems
    if doc["format"] != FORMAT:
        problems.append(f"format must be {FORMAT!r}")
    if doc["version"] != VERSION or isinstance(doc["version"], bool):
        problems.append(f"version must be {VERSION}")
    if app is not None and doc["app"] != app:
        problems.append(f"app is {doc['app']!r}, the registry name is {app!r}")
    mcp = doc["mcp"]
    if mcp is not None and exact(mcp, {"tools", "read_only", "approval_gated", "transports"}, "mcp", problems, {"dispatch"}):
        tools = set(names(mcp["tools"], "mcp.tools", problems))
        if "dispatch" in mcp:
            dispatch_problems(mcp["dispatch"], tools, problems)
        for key in ("read_only", "approval_gated"):
            for name in names(mcp[key], f"mcp.{key}", problems):
                if name not in tools:
                    problems.append(f"mcp.{key} names {name!r}, which is not in mcp.tools")
        transports = mcp["transports"]
        if not isinstance(transports, list) or not transports or not set(transports) <= TRANSPORTS or len(set(transports)) != len(transports):
            problems.append("mcp.transports must list one or both of stdio and http")
    skills = doc["skills"]
    if not isinstance(skills, list):
        problems.append("skills must be a list")
    else:
        seen = set()
        for i, skill in enumerate(skills):
            if exact(skill, {"name", "sub_skills"}, f"skills[{i}]", problems):
                if not isinstance(skill["name"], str) or not NAME.match(skill["name"]):
                    problems.append(f"skills[{i}].name must be a name")
                elif skill["name"] in seen:
                    problems.append(f"skills[{i}].name {skill['name']!r} is listed twice")
                seen.add(skill["name"])
                names(skill["sub_skills"], f"skills[{i}].sub_skills", problems)
    dock = doc["dock"]
    if exact(dock, {"present", "positions", "tabs"}, "dock", problems):
        if not isinstance(dock["present"], bool):
            problems.append("dock.present must be true or false")
        positions = dock["positions"]
        if not isinstance(positions, list) or not set(positions) <= POSITIONS or len(set(positions)) != len(positions):
            problems.append("dock.positions must list left, right, bottom or floating, each once")
        names(dock["tabs"], "dock.tabs", problems)
    extensions = doc["extensions"]
    if extensions is not None and exact(extensions, {"host_api"}, "extensions", problems):
        if not isinstance(extensions["host_api"], str) or not HOST_API.match(extensions["host_api"]):
            problems.append("extensions.host_api must be a version such as 1 or 1.2")
    return problems


def mcp_counts(mcp):
    found = {
        "tools": len(mcp["tools"]),
        "read_only": len(mcp["read_only"]),
        "approval_gated": len(mcp["approval_gated"]),
        "transports": sorted(mcp["transports"]),
    }
    if "dispatch" in mcp:
        found["dispatch"] = [{"tool": row["tool"], "reaches": row["reaches"]} for row in mcp["dispatch"]]
    return found


def counts(doc):
    mcp = doc["mcp"]
    return {
        "mcp": None if mcp is None else mcp_counts(mcp),
        "skills": {
            "count": len(doc["skills"]),
            "sub_skills": sum(len(s["sub_skills"]) for s in doc["skills"]),
            "names": [s["name"] for s in doc["skills"]],
        },
        "dock": {"present": doc["dock"]["present"], "positions": list(doc["dock"]["positions"]), "tabs": len(doc["dock"]["tabs"])},
        "extensions": None if doc["extensions"] is None else {"host_api": doc["extensions"]["host_api"]},
    }


def read(gh, repo, tag, app):
    try:
        text = gh.file_at(f"{ORG}/{repo}", PATH, tag)
    except ApiError as error:
        if error.status == 0 or error.status >= 500:
            raise
        print(f"::warning::{app} {tag}: {PATH} could not be read ({error.status}); its counts are left out")
        return None
    if text is None:
        return None
    try:
        doc = json.loads(text)
    except ValueError:
        print(f"::warning::{app} {tag}: {PATH} is not JSON; its counts are left out")
        return None
    found = problems_of(doc, app)
    if found:
        print(f"::warning::{app} {tag}: {PATH} does not follow the schema ({found[0]}); its counts are left out")
        return None
    return counts(doc)


def main():
    parser = argparse.ArgumentParser(description="check an app's agents/manifest.json against formadaptor's schema")
    parser.add_argument("command", choices=["check", "counts"])
    parser.add_argument("file")
    parser.add_argument("--app", help="the registry name the manifest must carry")
    args = parser.parse_args()
    try:
        doc = json.loads(Path(args.file).read_text(encoding="utf-8"))
    except (OSError, ValueError) as error:
        sys.exit(f"manifest: {args.file}: {error}")
    found = problems_of(doc, args.app)
    for problem in found:
        print(f"::error::{args.file}: {problem}")
    if found:
        return 1
    if args.command == "counts":
        print(json.dumps(counts(doc), indent=2))
    else:
        print(f"manifest: {args.file} follows {FORMAT} version {VERSION}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
