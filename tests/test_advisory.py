import json

from conftest import FIXTURES, REPO, client, contents, script

import advisory

VIS = json.loads((FIXTURES / "manifest.formvis.json").read_text(encoding="utf-8"))


def app(app_id, tag, skills=".claude/skills"):
    return {"id": app_id, "public": True, "name": app_id.capitalize(), "repository": f"nodemode-dev/{app_id}",
            "agents": {"mcp": True, "skills": skills}, "release": {"version": tag[1:], "tag": tag}}


def tree(*folders, truncated=False):
    items = [{"path": "README.md", "type": "blob"}] + [{"path": f".claude/skills/{f}/SKILL.md", "type": "blob"} for f in folders]
    return [200, {"truncated": truncated, "tree": items + [{"path": ".claude/skills/deep/x/SKILL.md", "type": "blob"}]}]


def family(*apps):
    return {"apps": [*apps, {"id": "formhidden", "public": False}, dict(app("formnone", "v1.0.0"), release=None)]}


def test_main_that_offers_what_the_release_does_reports_nothing():
    gh, fake = client({
        "/repos/nodemode-dev/formvis/contents/agents/manifest.json?ref=v2.3.5": contents(json.dumps(VIS)),
        "/repos/nodemode-dev/formvis/contents/agents/manifest.json?ref=main": contents(json.dumps(VIS)),
        "/repos/nodemode-dev/formvis/git/trees/v2.3.5?recursive=1": tree("formvis-harness"),
        "/repos/nodemode-dev/formvis/git/trees/main?recursive=1": tree("formvis-harness"),
    })
    assert advisory.check(gh, family(app("formvis", "v2.3.5"))) == []
    assert not any("formhidden" in p or "formnone" in p for _, p, _ in fake.calls)


def test_main_that_changes_tools_sub_skills_and_skill_folders_is_named():
    later = json.loads(json.dumps(VIS))
    later["mcp"]["tools"].append("crop_image")
    later["mcp"]["approval_gated"] = []
    later["skills"][0]["sub_skills"].remove("export")
    gh, _ = client({
        "/repos/nodemode-dev/formvis/contents/agents/manifest.json?ref=v2.3.5": contents(json.dumps(VIS)),
        "/repos/nodemode-dev/formvis/contents/agents/manifest.json?ref=main": contents(json.dumps(later, indent=2)),
        "/repos/nodemode-dev/formvis/git/trees/v2.3.5?recursive=1": tree("formvis-harness"),
        "/repos/nodemode-dev/formvis/git/trees/main?recursive=1": tree("formvis-harness", "formvis-export"),
    })
    assert advisory.check(gh, family(app("formvis", "v2.3.5"))) == [("Formvis", "v2.3.5", [
        "adds tools crop_image", "drops approval-gated tools export_image", "drops sub-skills of formvis-harness: export", "adds skill folders formvis-export"])]


def test_main_that_adds_or_changes_a_dispatching_tool_is_named():
    old = json.loads(json.dumps(VIS))
    old["mcp"]["dispatch"] = [{"tool": "apply_filter", "reaches": 289}]
    later = json.loads(json.dumps(VIS))
    later["mcp"]["dispatch"] = [{"tool": "apply_filter", "reaches": 300}, {"tool": "export_image", "reaches": 4}]
    assert advisory.manifest_differences(VIS, later) == ["adds dispatching tools apply_filter, export_image"]
    assert advisory.manifest_differences(old, later) == ["adds dispatching tools export_image", "apply_filter reaches 300 instead of 289"]
    assert advisory.manifest_differences(later, VIS) == ["drops dispatching tools apply_filter, export_image"]


def test_a_manifest_that_appears_or_breaks_on_main_is_named_and_a_failure_does_not_stop_the_others():
    gh, _ = client({
        "/repos/nodemode-dev/formcut/contents/agents/manifest.json?ref=main": contents(json.dumps(dict(VIS, app="formcut"))),
        "/repos/nodemode-dev/formvis/contents/agents/manifest.json?ref=v2.3.5": contents(json.dumps(VIS)),
        "/repos/nodemode-dev/formvis/contents/agents/manifest.json?ref=main": contents("{broken"),
        "/repos/nodemode-dev/formwav/git/trees/v2.26.3?recursive=1": tree("formwav-harness"),
        "/repos/nodemode-dev/formwav/git/trees/main?recursive=1": tree(truncated=True),
    })
    report = advisory.check(gh, family(app("formcut", "v2.15.8", skills=""), app("formvis", "v2.3.5", skills=""), app("formwav", "v2.26.3")))
    assert report[0] == ("Formcut", "v2.15.8", ["adds agents/manifest.json"])
    assert report[1] == ("Formvis", "v2.3.5", ["agents/manifest.json on main is not valid JSON"])
    assert report[2][0] == "Formwav" and "too large to list" in report[2][2][0]


def test_the_script_never_fails(tmp_path):
    (tmp_path / "family.json").write_text(json.dumps(family()))
    env = {"PATH": "/usr/bin:/bin", "GITHUB_API_URL": "http://127.0.0.1:9", "GITHUB_STEP_SUMMARY": str(tmp_path / "summary.md")}
    assert script("advisory.py", "--family", str(tmp_path / "missing.json"), env=env).returncode == 0
    result = script("advisory.py", "--family", str(tmp_path / "family.json"), env=env)
    assert result.returncode == 0
    assert "offers agents what its newest release does" in (tmp_path / "summary.md").read_text()


def test_the_hourly_run_calls_it_in_a_step_that_cannot_fail_the_job():
    text = (REPO / ".github" / "workflows" / "hourly.yml").read_text()
    step = text.split("- name: Main against the released tags (advisory)", 1)[1].split("- uses:", 1)[0]
    assert "continue-on-error: true" in step and "python3 -I scripts/advisory.py" in step
