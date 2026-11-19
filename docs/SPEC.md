# The family spec and the agent manifest

## family.json

Published at `https://github.com/nodemode-dev/formadaptor/blob/spec/family.json` (raw: `https://raw.githubusercontent.com/nodemode-dev/formadaptor/spec/family.json`) by the hourly workflow, only when its content changed. Schema: `spec/family.schema.json`.

| Field | Meaning |
| --- | --- |
| `format`, `format_version` | `formai-family`, `1`. |
| `generated` | When it was built. Not part of the content; never copy it. |
| `source` | `{"repository": "nodemode-dev/formcompiler", "registry_version": "<formcompiler VERSION>"}`. A consumer must not copy `registry_version` into a file it generates: the version moves with every compiler release, also one that changes nothing the consumer shows, and each copy would then drift for no visible reason. |
| `content_sha256` | SHA-256 of the document without `generated` and `content_sha256`, keys sorted, no whitespace. |
| `apps` | Every enabled registry entry, sorted by `id`. |

An app whose repository is private is `{"id": "<catalogue id>", "public": false}` and nothing else. A public app has the fields below. "Registry" is formcompiler's `apps/<registry name>.json` at `main`; every other source is named. formadaptor copies each value as it finds it and decides none of them.

| Field | Meaning | Comes from |
| --- | --- | --- |
| `id` | The catalogue id (`formslide` for FormDeck, `formai` for FormPortal). | Registry `catalog.id`. |
| `public` | `true`. | GitHub: `GET /repos/nodemode-dev/<repo>` answers 200 with `"private": false`. |
| `app` | Registry name. | Registry `app`. |
| `repo` | Repository name. | formadaptor's `spec/ids.json` `repo` (checked against the registry's `repository` on every build). |
| `repository` | `nodemode-dev/<repo>`. | Registry `repository`. |
| `site` | Path on formai.studio. | formadaptor's `spec/ids.json` `site`. |
| `name`, `kind`, `summary`, `licence` | Display name, kind, one-line summary, licence. | Registry `catalog.name`, `catalog.kind`, `catalog.summary`, `catalog.licence`. |
| `state` | The registry's state for the app (`live`, `public`, `prelaunch` today). | Registry `catalog.state`, and nothing else: not GitHub, not the release, not formai.studio's catalogue. |
| `launcher` | The command that starts the app. | Registry `build.cli`, else registry `app`. |
| `agents` | `{"mcp": bool, "skills": "<skills folder or empty>"}`. | Registry `agents.mcp` and `agents.skills`. |
| `release` | The newest published, non-draft, stable (`vX.Y.Z`), non-yanked release, or `null` when there is none. | GitHub: `GET /repos/nodemode-dev/<repo>/releases`, less the versions in formcompiler's `yanked.json`. |
| `release.version`, `release.tag`, `release.published`, `release.url` | `X.Y.Z`, the tag, when it was published, its page. | The release's `tag_name`, `published_at` (else `created_at`) and `html_url`. |
| `release.skills` | Skill folder names, sorted; left out when the release has no readable `form-app.json`. | The release asset `form-app.json`, `agents.skills.skills[].folder` (else `.name`), only when its `app` and `version` match. |
| `manifest` | Counts (below); left out when the file is missing or does not follow the schema. | `agents/manifest.json` in the app's repository at `release.tag` (`GET /repos/nodemode-dev/<repo>/contents/agents/manifest.json?ref=<tag>`). |

### What `state` is, and what else the spec carries

`state` is the registry's `catalog.state`, copied. formai.studio's catalogue can call an app live that the registry still calls `public` or `prelaunch` (six apps on 2026-11-18: FormPortal and FormEncoder `public`; FormMCP, FormSkills, FormPDF and FormTray `prelaunch`). Which source is right is the owner's decision; until it is made, a generator that lists "live" apps follows the registry. A generator that needs another rule can already build it from the spec without a new field: whether the app has a published stable release is `release` not being `null`, and its version and publication time are `release.version` and `release.published`. What formai.studio's own catalogue says is not in the spec: formadaptor does not read it.

## The agent manifest

Each app will write `agents/manifest.json` with its own `agents sync` and keep it true with `agents sync --check`. Schema: `spec/agent-manifest.schema.json`. Check a file with `python3 -I scripts/manifest.py check agents/manifest.json --app <registry name>`.

```json
{
  "format": "form-agent-manifest",
  "version": 1,
  "app": "formvis",
  "mcp": {
    "tools": ["open_image", "list_layers", "apply_filter", "export_image"],
    "read_only": ["list_layers"],
    "approval_gated": ["export_image"],
    "transports": ["stdio", "http"]
  },
  "skills": [{"name": "formvis-harness", "sub_skills": ["layers", "filters", "export"]}],
  "dock": {"present": true, "positions": ["right", "bottom"], "tabs": ["chat", "activity"]},
  "extensions": {"host_api": "1"}
}
```

Rules: every key is required and no other key is allowed, except the one optional field `mcp.dispatch` (below). `app` is the registry name. `mcp` is `null` when the app has no MCP server; otherwise `tools` lists every tool name the server lists, `read_only` the ones that change nothing, `approval_gated` the ones that wait for the person's approval in the app (both subsets of `tools`), and `transports` one or both of `stdio` and `http`. `skills` lists each skill folder the app ships with the names of its sub-skills (empty list for none). `dock.positions` uses `left`, `right`, `bottom`, `floating`; `dock.tabs` names the dock's tabs. `extensions` is `null` unless the app hosts form.ext extensions, then the host API version it implements. Names are `[A-Za-z0-9][A-Za-z0-9._-]*`, at most 80 characters, each once per list.

### `mcp.dispatch`: tools that run many commands

Some apps put most of what they offer behind one tool that takes a command or tool name (formlit's `run_command`, formdesign's `use_tool`), so `mcp.tools` alone says little of what the app can do. Such an app may add `mcp.dispatch`, a non-empty list with one object per dispatching tool:

```json
"dispatch": [{"tool": "run_command", "reaches": 289}]
```

`tool` is the dispatching tool's name; it must be in `mcp.tools`, once. `reaches` is a whole number of at least 1: how many commands or tools it can run that `mcp.tools` does not list. Like every other field it is written by the app's sync from its own registry of commands, never typed. An app with no such tool leaves the field out (not an empty list); a manifest without it stays valid and means the same as before.

### What the spec takes from the manifest

The spec carries counts, not the lists: `mcp.tools`, `mcp.read_only`, `mcp.approval_gated` (numbers) and `mcp.transports`, and `mcp.dispatch` as the same list of `tool` and `reaches`, present only when the manifest has it; `skills.count`, `skills.sub_skills` (total) and `skills.names`; `dock.present`, `dock.positions` and `dock.tabs` (number); `extensions.host_api`.
