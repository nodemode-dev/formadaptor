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

### manifest.py · counts from agents/manifest.json, or no counts at all
- refers-to: scripts/manifest.py :: problems_of, counts, read; spec/agent-manifest.schema.json; docs/SPEC.md :: The agent manifest
- kind: feature
- logged: v0.1.0 · 2026-11-18

No app ships `agents/manifest.json` yet. The spec builder reads it at the release tag and, when it is missing (404), leaves the app's `manifest` block out instead of guessing counts from `form-app.json` or the registry. The owner's wording: counts are then left out rather than guessed.

The lists in the manifest are names, not numbers (`mcp.tools`, `mcp.read_only`, `mcp.approval_gated`, `dock.tabs`, each skill's `sub_skills`), so an app's own `--check` can compare them with its code and a reader can see which tool is gated; the spec carries the counts. `read_only` and `approval_gated` must be subsets of `tools`.

`problems_of` is a hand-written check of the same rules as `spec/agent-manifest.schema.json`, because the scripts use the standard library only (no jsonschema). The two must change together. `manifest.py check FILE --app NAME` is there for an app's own sync step to call. A manifest that breaks a rule, is not JSON, or answers a 4xx other than 404 gives a warning and no counts; a 5xx or no answer stops the build, as visibility does.

Run 2026-11-18: a sample formvis manifest passed `check` (rc 0) and `counts` gave 4 tools, 1 read-only, 1 gated, 1 skill with 3 sub-skills, a dock on two sides with 2 tabs, host API 1; a broken copy named four problems (unknown field, wrong app, a read-only tool not in tools, an unknown dock position) and exited 1. Against the fake server, formvis's manifest at v2.3.5 gave the counts, formcut's broken one a warning and `None`, formtray's missing one `None` with no warning.

### spec.py · family.json, its content hash, and the spec branch
- refers-to: scripts/spec.py :: build, public_app, content_hash, changes, title, fetch, publish; spec/family.schema.json; docs/SPEC.md
- kind: feature
- logged: v0.1.0 · 2026-11-18

`build` takes every enabled registry entry, sorted by catalogue id. A private one becomes `{"id", "public": false}` and nothing else: no name, summary, version or repository name, and nothing about it is read beyond the one visibility call. A public one carries the registry's catalogue fields, the repository and site ids from `spec/ids.json`, the launcher (`build.cli`, else the registry name, as formMCP's generator takes it today), `agents` from the registry, the newest release (or `null`) and, when the app has `agents/manifest.json` at that tag, its counts. Disabled entries (formpublisher) are left out entirely, as every target leaves them out today. The build stops when `spec/ids.json` is not in step with the registry, so a new app cannot reach the spec without its id pair being reviewed.

`content_sha256` is the SHA-256 of the document without `generated` and itself, keys sorted, no whitespace. The hourly run compares it with the published file's, so a rebuild that finds nothing new publishes nothing; `generated` alone never counts as a change, and the generators must not copy it, or every target's `--check` would fail every hour.

The spec branch is written through the Git data API (blob, tree, commit, ref) with the workflow's built-in token, so no credential is put into a git remote. Each new commit has the previous one as parent, so `fetch --previous-out` can read the spec before it and `propose.py` can title its pull requests from the difference. The update is still sent with `force: true`, so an owner who resets the branch by hand does not break the next run.

`changes` names, per app: joins the family, is public, is no longer public (by id only), a new version, new agent counts, other details, leaves the family; when nothing per app changed but the registry version did, that. `title` keeps the first three and counts the rest.

Run 2026-11-18 against the fake server from the formcompiler copy: 30 enabled entries gave 23 public apps with their data and 7 bare private ids (formbench, formfabric, formnet, formpromo, formrec, formsculpt, formsurface; each object has exactly `id` and `public`). With formfabric's fixture answer changed from 404 to 200 the next build listed 24 public apps, FormFabric at 0.25.0 (0.25.1 is yanked), summary line "FormFabric is public", title `chore(family): FormFabric is public`, `changed=true` in the output file. A third build with nothing changed gave the same hash, `unchanged`, and the fallback title. `publish` then `publish` again and `fetch` against an in-process fake: the first commit had no parent and created the ref, the second had the first as parent and moved the ref, and `fetch` returned both files byte for byte.

### targets.json, propose.py · the target's own generator decides; formadaptor only proposes
- refers-to: targets.json; scripts/propose.py :: load_targets, plan, run_generator, generator_env, change_hash, propose, push; docs/TARGETS.md
- kind: feature
- logged: v0.1.0 · 2026-11-18

The family rule: a generated file is produced only by its own repository's generator. formadaptor holds no format of its own for a target's file; it runs `command --family <path> --check` in a clean checkout of the target at `main`, and only on exit 1 runs `command --family <path>` and reads `git status` for what changed. Any exit code other than 0 or 1 from `--check`, a non-zero exit from the write, a drift with no changed file, or a changed file outside the target's declared `files` (a path, or a folder ending in `/`) stops that target without proposing anything.

`command` is an argument list, never a shell string, so nothing in targets.json is interpreted by a shell. The generator runs with only `PATH`, `HOME`, `LANG`, `LC_ALL`, `TMPDIR` and `PYTHONDONTWRITEBYTECODE`: the App token minted for that target is not in its environment, and the workflow checks the target out with `persist-credentials: false`, so the generator cannot push or call the API. The contract says a generator never needs the network; it gets no credential to use one.

The branch is `<branch_prefix><first 10 hex of the change hash>`, where the change hash is the SHA-256 over each changed path and its new bytes. The same change gives the same branch, so a second run with the pull request still open proposes nothing; a different change gives a new branch, and every older open pull request from a `branch_prefix` branch of the same repository is commented "Superseded by #N", closed, and its branch deleted (a 404 or 422 on the delete means it is already gone). Pull requests from forks and from other branches are left alone. The commit is made as `nodemode-ai <mackin@nodemode.ai>`, the family's one identity, with the title as subject and the body as message.

The push sends the token as an `http.<base>/.extraheader` for that one command, so it is never written into `.git/config`. `FORMADAPTOR_GIT_BASE` (default `https://github.com`) moves the push to another address; it exists so the push could be run against a local bare repository.

formtray and form.ext are listed with `enabled: false`: neither has a generator yet. A disabled target is skipped with a notice. The owner turns each on once its generator has landed on the target's `main` (docs/OWNER_SETUP.md).

Run 2026-11-18 on /tmp/formadaptor-target-formMCP (formMCP's committed `core/data/family.json` and a stand-in `setup/family.py` that follows the contract): `--dry-run` with the spec where FormFabric had just gone public printed branch `bot/formadaptor-4626ce56ed`, the one file `core/data/family.json` and the title `chore(family): FormFabric is public`. With an in-process fake GitHub and a bare repository at file:///tmp/formadaptor-remote, the real path pushed that branch (commit by nodemode-ai, the token absent from `.git/config`), opened pull request 9, commented on and closed the older bot pull request 7 and deleted its branch, and left the non-bot pull request 8 alone. After that branch was merged into the checkout's main, the run said "in step with the family spec, nothing to propose" and changed nothing. A stand-in that also wrote `stray.txt` was refused by name. `matrix` listed the three enabled targets; formtray said it is disabled.

### hourly.yml · minute 33, build with a read-only token, publish in its own job
- refers-to: .github/workflows/hourly.yml :: spec, publish, propose
- kind: feature
- logged: v0.1.0 · 2026-11-18

Minute 33 because formcompiler's workflows start at 0, 15, 30, 45 and 17 and formpipe's at 47. This hourly run is the "has an app just gone public" check: the visibility call is what notices.

The rules are formcompiler's: every action pinned to a full commit SHA with its version as a trailing comment (the same pins formcompiler uses, since no other could be looked up here), no `${{ }}` inside `run:`, `contents: read` at the top and widened only for `publish`, and `persist-credentials: false` on every checkout. The fork guard `github.repository == 'nodemode-dev/formadaptor'` is on every job, with `github.ref == 'refs/heads/main'`, so a fork's copy of the schedule does nothing and a dispatch from another branch publishes nothing. In formcompiler that reason sits in a YAML comment above each guard; here it lives only in this log.

`spec` builds with the built-in token, which reads public repositories only, and hands `family.json` to `publish` as an artifact only when `content_sha256` differs from the published file's. `publish` is the one job with `contents: write`, and writes only the `spec` branch. `propose` calls propose.yml after a publish, passing the two App secrets by name rather than `secrets: inherit`. A failed proposal is retried by dispatching propose.yml by hand; the next hourly run proposes only when the spec changes again.

### propose.yml · one job per target, one token per target
- refers-to: .github/workflows/propose.yml :: targets, propose
- kind: feature
- logged: v0.1.0 · 2026-11-18

`targets` lists the enabled targets from targets.json; `propose` runs once per target with `fail-fast: false`, so one broken target does not hold back the others. The App token is minted with formcompiler's pinned `actions/create-github-app-token` (v3.3.0) the same way formcompiler's release job does it (`client-id` from the `_APP_ID` secret, `owner: nodemode-dev`), but for `repositories: <that one target>` with `permission-contents: write` and `permission-pull-requests: write` only. The target is checked out at `main` with that token and `persist-credentials: false`; the token reaches only propose.py, through `FORMADAPTOR_TARGET_TOKEN`, and propose.py keeps it out of the generator's environment.

A dispatch may name one target; every step of the other matrix rows is skipped. `workflow_call` declares the same `target` input so `inputs.target` is defined on both paths.

### self-check.yml · formcompiler's self-check, for this tree
- refers-to: .github/workflows/self-check.yml :: test, lint
- kind: feature
- logged: v0.1.0 · 2026-11-18

The same jobs as formcompiler's self-check: pytest, actionlint 1.7.12 checked against formcompiler's recorded SHA-256 of the release archive, `py_compile`, and the no-em-dash-in-Markdown, no-emoji scan, unchanged. Two checks are this repository's own: `registry.py ids --check` against a checkout of formcompiler's `main`, so a registry change that breaks an id pair is seen on the next push or pull request here, and `propose.py matrix`, which loads and validates targets.json.

Run 2026-11-18: actionlint v1.7.12 built with `go install` (behind /tmp/form-heavy-A.lock) passed hourly.yml, propose.yml and self-check.yml with no finding.
