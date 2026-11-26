import re

import pytest

from conftest import REPO, VERSION_SITES

WORKFLOWS = sorted((REPO / ".github" / "workflows").glob("*.yml"))
GUARD = "github.repository == 'nodemode-dev/formadaptor'"


def jobs(text):
    found = {}
    current = None
    for line in text.split("jobs:\n", 1)[1].splitlines():
        head = re.match(r"^  ([a-z][a-z0-9-]*):$", line)
        if head:
            current = head.group(1)
            found[current] = []
        elif current:
            found[current].append(line)
    return {name: "\n".join(lines) for name, lines in found.items()}


@pytest.mark.parametrize("path", WORKFLOWS, ids=lambda p: p.name)
def test_every_action_is_pinned_to_a_commit_with_its_version(path):
    for line in path.read_text().splitlines():
        if "uses: " in line and "uses: ./" not in line:
            assert re.search(r"uses: [\w.-]+/[\w./-]+@[0-9a-f]{40} # v\d", line), line


@pytest.mark.parametrize("path", WORKFLOWS, ids=lambda p: p.name)
def test_no_expression_inside_a_run_script(path):
    lines = path.read_text().splitlines()
    for i, line in enumerate(lines):
        if re.match(r"^\s+run: ", line):
            assert "${{" not in line, line
            if line.rstrip().endswith("|"):
                indent = len(line) - len(line.lstrip()) + 2
                for following in lines[i + 1:]:
                    if following.strip() and len(following) - len(following.lstrip()) < indent:
                        break
                    assert "${{" not in following, following


@pytest.mark.parametrize("path", WORKFLOWS, ids=lambda p: p.name)
def test_scripts_run_isolated(path):
    for line in path.read_text().splitlines():
        if re.search(r"python3 (adaptor/)?scripts/", line):
            pytest.fail(line)


@pytest.mark.parametrize("name", ["hourly.yml"])
def test_every_job_that_publishes_or_proposes_is_guarded(name):
    for job, body in jobs((REPO / ".github" / "workflows" / name).read_text()).items():
        assert GUARD in body and "github.ref == 'refs/heads/main'" in body, f"{name}: {job}"


def test_least_permissions():
    for path in WORKFLOWS:
        text = path.read_text()
        assert "\npermissions:\n  contents: read\n" in text, path.name
    hourly = jobs((REPO / ".github" / "workflows" / "hourly.yml").read_text())
    assert [name for name, body in hourly.items() if "contents: write" in body] == ["publish"]


def test_the_hourly_run_is_at_minute_33():
    assert 'cron: "33 * * * *"' in (REPO / ".github" / "workflows" / "hourly.yml").read_text()


def test_no_workflow_holds_a_secret():
    assert [p.name for p in WORKFLOWS] == ["hourly.yml", "self-check.yml"]
    for path in WORKFLOWS:
        text = path.read_text()
        assert "secrets." not in text and "FORMADAPTOR_APP" not in text, path.name
        assert text.count("persist-credentials: false") == text.count("actions/checkout@"), path.name


def test_every_version_site_agrees():
    found = {}
    for name, pattern in VERSION_SITES:
        match = re.search(pattern, (REPO / name).read_text(encoding="utf-8"), re.M)
        assert match, name
        found[name] = match.group(1)
    assert set(found.values()) == {"0.3.0"}, found
