# The family spec and the agent manifest

## family.json

Published at `https://github.com/nodemode-dev/formadaptor/blob/spec/family.json` (raw: `https://raw.githubusercontent.com/nodemode-dev/formadaptor/spec/family.json`) by the hourly workflow, only when its content changed. Schema: `spec/family.schema.json`.

| Field | Meaning |
| --- | --- |
| `format`, `format_version` | `formai-family`, `1`. |
| `generated` | When it was built. Not part of the content; never copy it. |
| `source` | `{"repository": "nodemode-dev/formcompiler", "registry_version": "<formcompiler VERSION>"}`. |
| `content_sha256` | SHA-256 of the document without `generated` and `content_sha256`, keys sorted, no whitespace. |
| `apps` | Every enabled registry entry, sorted by `id`. |

An app whose repository is private is `{"id": "<catalogue id>", "public": false}` and nothing else. A public app has:

| Field | Meaning |
| --- | --- |
| `id` | The catalogue id (`formslide` for FormDeck, `formai` for FormPortal). |
| `public` | `true`. |
| `app`, `repo`, `repository`, `site` | Registry name, repository name, `nodemode-dev/<repo>`, path on formai.studio (spec/ids.json). |
| `name`, `kind`, `summary`, `licence`, `state` | From the registry's `catalog`. |
| `launcher` | The registry's `build.cli`, else the registry name. |
| `agents` | `{"mcp": bool, "skills": "<skills folder or empty>"}` from the registry. |
| `release` | The newest published, non-draft, stable, non-yanked release: `version`, `tag`, `published`, `url`, and `skills` (folder names from its `form-app.json`) when it has one. `null` when there is none. |
| `manifest` | Counts from `agents/manifest.json` at that tag; left out when the file is missing or does not follow the schema. |

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

Rules: every key is required and no other key is allowed. `app` is the registry name. `mcp` is `null` when the app has no MCP server; otherwise `tools` lists every tool name the server lists, `read_only` the ones that change nothing, `approval_gated` the ones that wait for the person's approval in the app (both subsets of `tools`), and `transports` one or both of `stdio` and `http`. `skills` lists each skill folder the app ships with the names of its sub-skills (empty list for none). `dock.positions` uses `left`, `right`, `bottom`, `floating`; `dock.tabs` names the dock's tabs. `extensions` is `null` unless the app hosts form.ext extensions, then the host API version it implements. Names are `[A-Za-z0-9][A-Za-z0-9._-]*`, at most 80 characters, each once per list.

The spec carries counts, not the lists: `mcp.tools`, `mcp.read_only`, `mcp.approval_gated` (numbers) and `mcp.transports`; `skills.count`, `skills.sub_skills` (total) and `skills.names`; `dock.present`, `dock.positions` and `dock.tabs` (number); `extensions.host_api`.
