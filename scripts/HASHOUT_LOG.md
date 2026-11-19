# HASHOUT_LOG · adaptor · formadaptor

Living log of all comment content, explainers, rationale, TODOs and removed code for the adaptor (the scripts and the workflows). The source files stay comment-free per dev-rules `sub-skills/hashout-log/SUB-SKILL.md`; everything they would have said lives here, indexed. Read this first, then edit code surgically.

Current build version: v0.1.0
Last updated: 2026-11-18 · the first build: ids, the GitHub helper, registry, visibility, releases, the agent manifest, the family spec, targets and the propose step, three workflows (v0.1.0)

### github_api.py · one client, one transport, nothing global
- refers-to: scripts/github_api.py :: GitHub, urllib_transport, file_at, asset
- kind: feature
- logged: v0.1.0 · 2026-11-18

Modelled on formcompiler's `scripts/github_api.py` (same headers, the same `ApiError(status, message)`, the same Link-header paging), with one difference: the calls hang off a `GitHub` object whose `transport(method, url, headers, data)` returns `(status, headers, body)`. The default transport is urllib; tests pass a function that answers from fixtures, so no test opens a socket. `GITHUB_API_URL` moves the whole client to another address, which is how a local fake server was used during the build.

`call` returns every HTTP answer, error or not, so `visibility.py` can read a 404 as "private" without an exception; `request` raises `ApiError` for anything at or above 300. A transport failure (no answer at all) is `ApiError(0, ...)`, never a status a caller could take for 404.

`file_at` answers `None` for 404 because a missing `agents/manifest.json` is the normal case until the apps gain one. `paged` stops at 1000 items so a looping Link header cannot run forever.

The token is `GH_TOKEN` unless one is passed. The hourly workflow gives it the built-in token, which can read public repositories only, so the client never sees anything private.

Run 2026-11-18 against a local server on 127.0.0.1:25100: `get` read a repository, `paged` followed one `rel="next"` link and returned both pages, a 404 raised `ApiError` with status 404, and `file_at` answered `None` for a missing file.

### registry.py · the registry is read, never copied; ids.json is checked against it
- refers-to: scripts/registry.py :: load, ids, id_problems; spec/ids.json
- kind: feature
- logged: v0.1.0 · 2026-11-18

formcompiler stays the source of truth for which apps exist. `load` reads `apps/*.json` from a checkout (the workflows check out `nodemode-dev/formcompiler` at `main`) and asks only for the fields formadaptor uses: `app`, `repository`, `enabled` and the catalogue's `id`, `name`, `kind`, `summary`, `licence`, `state`. Full validation stays formcompiler's own `registry.py check`; this one refuses only what would make the spec wrong (a missing field, a file name that is not the app, a repository outside nodemode-dev).

`spec/ids.json` is hand-written and committed so a reviewer sees the id pairs in one place. `ids --check` compares its `repo` and `catalog` with the registry and refuses an id used twice. `site` is not compared: today the site path is the catalogue id for every app, and the file is where they would part if the site ever moved an app. The registry version is formcompiler's `VERSION`, not its commit, so a registry commit that changes nothing formadaptor reads does not change the spec.

Run 2026-11-18 on a copy of the formcompiler clone in /tmp/formadaptor-smoke: 31 entries, 30 enabled, `ids --check` in step (rc 0); with formdeck's catalogue id changed to `formdeck` in the copy it named that one problem (rc 1); a folder that is not a checkout stopped with a message (rc 1).

### visibility.py · 200 with private false is public; every other answer is private, except no answer
- refers-to: scripts/visibility.py :: public, STOP
- kind: feature
- logged: v0.1.0 · 2026-11-18

The owner's rule: public lists carry only apps whose repository is public. `GET /repos/nodemode-dev/<repo>` with the workflow's built-in token sees public repositories and nothing private outside formadaptor, so a 200 whose `private` is `false` is public and 404 (or 401, or a 403 that is not a rate limit, or a body that is not an object) is private. A missing `private` field counts as private, as in formcompiler's `catalog.py`.

One exception, on purpose: a 429, a 5xx, a 403 with `x-ratelimit-remaining: 0` or no answer at all stops the build with `ApiError`. Read as "private", a GitHub outage would build a spec with every app private, publish it, and propose pull requests that empty every target's list. Stopping keeps the published spec as it was until the next hourly run.

Run 2026-11-18 against the fake server on 127.0.0.1:25101 built from the clones: formvis and formcut answered public, formfabric and formREC (no clone, so 404) private.

### releases.py · the newest published stable release that is not yanked
- refers-to: scripts/releases.py :: newest, latest, load_yanked, form_app_skills
- kind: feature
- logged: v0.1.0 · 2026-11-18

The owner's decision: the spec follows released tags. `newest` takes, from the app repository's own releases, those that are not drafts, not prereleases and tagged `v<x.y.z>` with no prerelease part, drops every `(app, version)` in formcompiler's `yanked.json` (the same rows and the same shape check as formcompiler's `yank.load`), and keeps the highest by integer parts. This is the catalogue's stable channel in `catalog.py`; betas are left to the catalogue.

formcompiler's `releases.json` was not used as the source: it is the signed catalogue the private publishing pipeline writes after a release, so it lags a publish by one pipeline run, and it already leaves out private repositories by its own rule. Asking the repository directly is one call per public app and has no lag. A repository whose releases answer 404 has no release (`None`), and the app is listed with `release: null`.

`form_app_skills` reads the release's `form-app.json` asset (format_version 2, formcompiler `docs/REGISTRY.md`, `agents`) and keeps the skill folder names. An asset that cannot be read, or names another app or version, is left out with a warning rather than stopping the family.

Run 2026-11-18 against the fake server: formvis gave 2.3.5 with its skill list, past a newer draft and a newer beta; formtray gave 0.16.2 with no skills (it has no skills folder); formfabric (404) gave `None`; with formvis 2.3.5 marked yanked it fell back to the older 0.1.0. The yanked set read from the formcompiler clone holds formfabric 0.25.1, formsculpt 1.21.0 and formsurface 0.62.1.
