import base64
import json
import os
import re
import sys
import urllib.error
import urllib.parse
import urllib.request

ORG = "nodemode-dev"
USER_AGENT = "formadaptor"


class ApiError(Exception):
    def __init__(self, status, message):
        super().__init__(f"{status}: {message}")
        self.status = status


def urllib_transport(method, url, headers, data):
    req = urllib.request.Request(url, data=data, headers=headers, method=method)
    try:
        with urllib.request.urlopen(req, timeout=60) as response:
            return response.status, dict(response.headers), response.read()
    except urllib.error.HTTPError as error:
        return error.code, dict(error.headers or {}), error.read()


class GitHub:
    def __init__(self, base=None, token=None, transport=None):
        self.base = (base or os.environ.get("GITHUB_API_URL") or "https://api.github.com").rstrip("/")
        self.token = os.environ.get("GH_TOKEN", "").strip() if token is None else token
        self.transport = transport or urllib_transport

    def call(self, method, path, body=None, accept="application/vnd.github+json"):
        url = path if path.startswith("http") else f"{self.base}{path}"
        headers = {"Accept": accept, "X-GitHub-Api-Version": "2022-11-28", "User-Agent": USER_AGENT}
        if self.token:
            headers["Authorization"] = f"Bearer {self.token}"
        data = None
        if body is not None:
            data = json.dumps(body).encode("utf-8")
            headers["Content-Type"] = "application/json"
        try:
            status, answer_headers, payload = self.transport(method, url, headers, data)
        except OSError as error:
            raise ApiError(0, f"{method} {url}: {error}") from None
        return status, {k.lower(): v for k, v in (answer_headers or {}).items()}, payload or b""

    def request(self, method, path, body=None):
        status, headers, payload = self.call(method, path, body)
        if status >= 300:
            detail = payload.decode("utf-8", "replace")[:300]
            raise ApiError(status, f"{method} {path}: {detail}")
        return (json.loads(payload) if payload else None), headers.get("link", "")

    def get(self, path):
        return self.request("GET", path)[0]

    def paged(self, path, limit=1000):
        url = path + ("&" if "?" in path else "?") + "per_page=100"
        items = []
        while url and len(items) < limit:
            data, link = self.request("GET", url)
            items.extend(data)
            found = re.search(r'<([^>]+)>;\s*rel="next"', link or "")
            url = found.group(1) if found else ""
        return items

    def file_at(self, repo, path, ref):
        quoted = urllib.parse.quote(path)
        status, _, payload = self.call("GET", f"/repos/{repo}/contents/{quoted}?ref={urllib.parse.quote(ref)}")
        if status == 404:
            return None
        if status >= 300:
            raise ApiError(status, f"GET {repo}:{path} at {ref}: {payload.decode('utf-8', 'replace')[:300]}")
        data = json.loads(payload)
        if not isinstance(data, dict) or data.get("encoding") != "base64":
            raise ApiError(0, f"{repo}:{path} at {ref} is not a file")
        return base64.b64decode(data["content"]).decode("utf-8")

    def asset(self, url):
        status, _, payload = self.call("GET", url, accept="application/octet-stream")
        if status >= 300:
            raise ApiError(status, f"GET {url}")
        return payload


def summary(text):
    path = os.environ.get("GITHUB_STEP_SUMMARY")
    if path:
        with open(path, "a", encoding="utf-8") as handle:
            handle.write(text)
    sys.stdout.write(text)


def output(name, value):
    path = os.environ.get("GITHUB_OUTPUT")
    if path:
        with open(path, "a", encoding="utf-8") as handle:
            handle.write(f"{name}={value}\n")
