import base64
import json
import subprocess
import sys
from pathlib import Path

import pytest

REPO = Path(__file__).resolve().parents[1]
SCRIPTS = REPO / "scripts"
FIXTURES = Path(__file__).resolve().parent / "fixtures"
VERSION_SITES = [
    ("VERSION", r"^(\S+)$"),
    ("CHANGELOG.md", r"^## v(\S+) ·"),
    ("scripts/HASHOUT_LOG.md", r"^Current build version: v(\S+)$"),
]

sys.path.insert(0, str(SCRIPTS))

import github_api


def script(name, *args, cwd=None, env=None):
    return subprocess.run([sys.executable, "-I", str(SCRIPTS / name), *args], cwd=cwd or REPO, capture_output=True, text=True, timeout=120, env=env)


class Fake:
    def __init__(self, routes):
        self.routes = routes
        self.calls = []

    def __call__(self, method, url, headers, data):
        path = url.split("http://fake", 1)[1]
        self.calls.append((method, path, json.loads(data) if data else None))
        bare = path.replace("?per_page=100", "").replace("&per_page=100", "")
        answer = self.routes.get((method, bare)) or self.routes.get(bare)
        if answer is None:
            return 404, {}, b'{"message": "Not Found"}'
        status, body = answer[0], answer[1]
        headers = answer[2] if len(answer) > 2 else {}
        return status, headers, body if isinstance(body, bytes) else json.dumps(body).encode("utf-8")


def client(routes):
    fake = Fake(routes)
    return github_api.GitHub(base="http://fake", token="", transport=fake), fake


def contents(text):
    return [200, {"encoding": "base64", "content": base64.b64encode(text.encode("utf-8")).decode("ascii")}]


def entry(app, repo, catalog_id, name, enabled=True, skills=".claude/skills", mcp=True, cli=None):
    data = {
        "app": app, "repository": f"nodemode-dev/{repo}", "title": app, "enabled": enabled,
        "build": {"mode": "contract", "cli": cli or app},
        "catalog": {"id": catalog_id, "name": name, "kind": "image", "summary": f"{name} does things.", "identifier": f"ai.nodemode.{app}",
                    "licence": "Apache-2.0", "state": "live"},
        "agents": {"skills": skills, "mcp": mcp},
    }
    if not enabled:
        data["disabled_reason"] = "Not yet."
    return data


MINI = [
    entry("formvis", "formvis", "formvis", "FormVis"),
    entry("formdeck", "formdeck", "formslide", "FormDeck"),
    entry("formsecret", "formSecret", "formsecret", "FormSecret"),
    entry("formlater", "formlater", "formlater", "FormLater", enabled=False),
]


@pytest.fixture
def compiler(tmp_path):
    root = tmp_path / "compiler"
    (root / "apps").mkdir(parents=True)
    for data in MINI:
        (root / "apps" / f"{data['app']}.json").write_text(json.dumps(data), encoding="utf-8")
    (root / "VERSION").write_text("0.16.0\n", encoding="utf-8")
    (root / "yanked.json").write_text(json.dumps({"yanked": [{"app": "formdeck", "version": "0.40.0", "reason": "r", "date": "2026-11-17"}]}), encoding="utf-8")
    rows = [{"app": d["app"], "repo": d["repository"].split("/")[1], "catalog": d["catalog"]["id"], "site": d["catalog"]["id"]} for d in MINI]
    ids = tmp_path / "ids.json"
    ids.write_text(json.dumps({"format": "formadaptor-ids", "format_version": 1, "apps": sorted(rows, key=lambda r: r["app"])}), encoding="utf-8")
    return root, ids


@pytest.fixture
def routes():
    manifest = (FIXTURES / "manifest.formvis.json").read_text(encoding="utf-8")
    return {
        "/repos/nodemode-dev/formvis": [200, {"private": False}],
        "/repos/nodemode-dev/formdeck": [200, {"private": False}],
        "/repos/nodemode-dev/formvis/releases": [200, [
            {"tag_name": "v2.4.0", "draft": True},
            {"tag_name": "v2.4.0-beta.1", "prerelease": True, "published_at": "2026-11-18T00:00:00Z"},
            {"tag_name": "v2.3.5", "published_at": "2026-11-17T12:00:00Z", "html_url": "https://github.com/nodemode-dev/formvis/releases/tag/v2.3.5",
             "assets": [{"name": "form-app.json", "browser_download_url": "http://fake/dl/formvis/form-app.json"}]},
            {"tag_name": "v2.10.0-rc.1", "prerelease": True},
            {"tag_name": "v1.99.9", "published_at": "2026-10-01T00:00:00Z"},
        ]],
        "/dl/formvis/form-app.json": [200, {"app": "formvis", "version": "2.3.5", "agents": {"skills": {"skills": [{"folder": "formvis-harness"}]}}}],
        "/repos/nodemode-dev/formvis/contents/agents/manifest.json?ref=v2.3.5": contents(manifest),
        "/repos/nodemode-dev/formdeck/releases": [200, [
            {"tag_name": "v0.40.0", "published_at": "2026-11-18T00:00:00Z"},
            {"tag_name": "v0.39.0", "published_at": "2026-11-17T00:00:00Z", "html_url": "https://github.com/nodemode-dev/formdeck/releases/tag/v0.39.0"},
        ]],
    }
