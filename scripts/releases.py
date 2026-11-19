import json
import re
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from github_api import ORG, ApiError

STABLE_TAG = re.compile(r"^v((0|[1-9]\d*)\.(0|[1-9]\d*)\.(0|[1-9]\d*))$")


def load_yanked(compiler):
    path = Path(compiler) / "yanked.json"
    if not path.is_file():
        return frozenset()
    data = json.loads(path.read_text(encoding="utf-8"))
    rows = data.get("yanked") if isinstance(data, dict) else None
    if not isinstance(rows, list) or not all(isinstance(r, dict) and {"app", "version"} <= r.keys() for r in rows):
        raise ValueError("yanked.json must be {\"yanked\": [{\"app\", \"version\", ...}]}")
    return frozenset((row["app"], row["version"]) for row in rows)


def key(version):
    return tuple(int(part) for part in version.split("."))


def newest(release_list, app, yanked=frozenset()):
    best = None
    for release in release_list:
        found = STABLE_TAG.match(release.get("tag_name") or "")
        if not found or release.get("draft") or release.get("prerelease"):
            continue
        version = found.group(1)
        if (app, version) in yanked:
            continue
        if best is None or key(version) > key(best[0]):
            best = (version, release)
    return best


def form_app_skills(gh, release, app, version):
    asset = next((a for a in release.get("assets") or [] if a.get("name") == "form-app.json"), None)
    if not asset or not asset.get("browser_download_url"):
        return None
    try:
        data = json.loads(gh.asset(asset["browser_download_url"]))
    except (ApiError, ValueError):
        print(f"::warning::{app} {version}: form-app.json could not be read; its skills are left out")
        return None
    if data.get("app") != app or data.get("version") != version:
        print(f"::warning::{app} {version}: form-app.json names {data.get('app')} {data.get('version')}; its skills are left out")
        return None
    skills = ((data.get("agents") or {}).get("skills") or {}).get("skills") or []
    return sorted(str(s.get("folder") or s.get("name")) for s in skills if isinstance(s, dict))


def latest(gh, repo, app, yanked=frozenset()):
    try:
        release_list = gh.paged(f"/repos/{ORG}/{repo}/releases")
    except ApiError as error:
        if error.status == 404:
            return None
        raise
    found = newest(release_list, app, yanked)
    if not found:
        return None
    version, release = found
    block = {
        "version": version,
        "tag": release["tag_name"],
        "published": release.get("published_at") or release.get("created_at") or "",
        "url": release.get("html_url") or f"https://github.com/{ORG}/{repo}/releases/tag/{release['tag_name']}",
    }
    skills = form_app_skills(gh, release, app, version)
    if skills is not None:
        block["skills"] = skills
    return block
