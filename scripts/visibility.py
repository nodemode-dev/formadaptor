import argparse
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from github_api import ORG, ApiError, GitHub

STOP = (429, 500, 502, 503, 504)


def public(gh, repo):
    status, headers, payload = gh.call("GET", f"/repos/{ORG}/{repo}")
    if status in STOP or (status == 403 and headers.get("x-ratelimit-remaining") == "0"):
        raise ApiError(status, f"GET /repos/{ORG}/{repo}: GitHub did not answer, so no visibility is known")
    if status != 200:
        return False
    try:
        data = json.loads(payload)
    except ValueError:
        return False
    return isinstance(data, dict) and data.get("private") is False


def visibilities(gh, repos):
    return {repo: public(gh, repo) for repo in repos}


def main():
    parser = argparse.ArgumentParser(description="which nodemode-dev repositories answer as public")
    parser.add_argument("repos", nargs="+")
    args = parser.parse_args()
    try:
        found = visibilities(GitHub(), args.repos)
    except ApiError as error:
        sys.exit(f"::error::{error}")
    for repo, is_public in found.items():
        print(f"{repo}: {'public' if is_public else 'private'}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
