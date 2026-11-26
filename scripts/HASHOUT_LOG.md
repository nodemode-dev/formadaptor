# HASHOUT_LOG · adaptor · formadaptor

Living log of all comment content, explainers, rationale, TODOs and removed code for the adaptor (the scripts and the workflows). The source files stay comment-free per dev-rules `sub-skills/hashout-log/SUB-SKILL.md`; everything they would have said lives here, indexed. Read this first, then edit code surgically.

Current build version: v0.2.3
Last updated: 2026-11-25 · FormCraft's and FormRig's id pairs (v0.2.3)

### propose.py · plan, changed and apply; no secret in this repository
- refers-to: scripts/propose.py :: plan_command, write_plan, changed_plans, checked_plan, apply_plan, apply_command; .github/workflows/hourly.yml; tests/test_workflows.py :: test_no_workflow_holds_a_secret
- kind: change
- logged: v0.3.0 · 2026-11-26

The owner ruled that formadaptor holds no secret. Proposing moves to formcompiler's `adaptor.yml`, which holds formcompiler's release App. formcompiler's rule is that a job holding its release credential never runs another repository's code, and a target's generator is exactly that, so `run` is split in two. `run` stays, for a local dry run and for anything that still calls it.

`plan` does what `run` does up to `plan(...)` and writes the result into a new, empty folder: `proposal.json` (format `formadaptor-plan`, version 1) and `files/<path>`, a byte copy of each changed file that still exists. The proposal dict now carries `change_hash`, the full digest the branch name is cut from, so `apply` can compare without running anything. In the plan file the changed paths are `paths` and `files` is the list of `{path, sha256}` or `{path, deleted: true}`. `base` is the checkout's HEAD before the generator ran; a generator that moves HEAD is refused. A file the generator leaves as a link, or a path that goes through a link in the checkout, is refused rather than copied. It writes `changed=true|false`; nothing to propose writes no plan.

`changed --plans DIR` lists, as `matrix` does, the enabled targets that have a `plan-<name>/proposal.json` naming that target. Anything else is skipped with a `::warning::` on stderr, never a failure, and a missing or empty folder is `[]`.

`apply` trusts nothing in the plan, because the job that wrote it ran the target's code. Before it touches the checkout it checks: format and version; target and repository against targets.json; base a 40-hex sha and change hash a 64-hex sha; the branch is the target's `branch_prefix` and the first 10 characters of that hash (stricter than "starts with the prefix", and it is what `plan` writes); every path relative, without `..`, `.` or empty parts, backslash or control character, and `allowed` by the target's files; `paths` exactly the sorted listed files; every entry under `files/` a plain file that is listed and matches its sha256, no link anywhere, and every listed copy present. Title and body are passed on as text, cut at 200 and 60,000 characters. Untrusted values in error lines are quoted with `repr`, so a name with a newline cannot start a workflow command; the plan's warning reaches the summary with control characters replaced and is not printed as `::warning::` (the plan job already did that).

If the checkout's HEAD is not the plan's base, `apply` writes one summary line, `proposed=false`, exits 0 and pushes nothing. Otherwise it refuses a dirty checkout or a path that goes through a link in the checkout, copies and deletes, and refuses unless `git status` names exactly the plan's paths and `change_hash` over them equals the plan's. Then `propose(...)` as `run` calls it, with the same summary lines and `proposed` output. It runs no generator and nothing from the checkout.

hourly.yml loses its `propose` job and propose.yml is gone; the workflow test that read propose.yml's App token now checks that no workflow here names a secret.

Rehearsed 2026-11-26 in a scratch folder with a local bare repository as the target, `FORMADAPTOR_GIT_BASE` pointing at it and a local stand-in for the API: plan wrote two files and `changed=true`; changed listed the one good plan and warned on four bad entries; apply refused a path outside the target's files, a wrong sha256, a link in the plan, another repository, a `..` path and a branch outside the prefix, each before touching the checkout; the real apply pushed `bot/formadaptor-b61b29ee1d` as nodemode-ai and opened the stand-in pull request; after main moved it wrote the one line and `proposed=false`. The suite: 82 passed.

### ids.json · rows 36 and 37, FormCraft and FormRig
- refers-to: spec/ids.json; tests/test_sources.py :: test_ids_file_pairs_every_registry_entry_once
- kind: fix
- logged: after v0.2.2 · 2026-11-25

formcompiler's `main` registers FormRig (`apps/formrig.json`, `nodemode-dev/formrig`, catalogue id `formrig`) and FormCraft (`apps/formcraft.json`, `nodemode-dev/formcraft`, catalogue id `formcraft`), added there in its 0.22.0. `spec/ids.json` had no row for either, and `ids --check` compares every registry entry, so the `lint` job stopped on both names as soon as this repository's 0.2.2 reached `main`, and the hourly build would stop the same way. FormPromo, registered at the same time, already had its row.

Each gets one row, in the file's alphabetical place: FormCraft after FormCel, FormRig after FormRef. App, repository, catalogue id and site id are the same word for both. The test counts 37 rows and 37 different catalogue ids.

Run 2026-11-25 against formcompiler's `main` at its 37 entries: before, `ids --check` named `formcraft` and `formrig` as "in the registry, not in spec/ids.json" and left with 1; after, it reports the 37 entries in step.

### ids.json · rows 34 and 35, FormSubstrate and FormSlot, both switched off in the registry
- refers-to: spec/ids.json; tests/test_sources.py :: test_ids_file_pairs_every_registry_entry_once
- kind: change
- logged: v0.2.2 · 2026-11-22

formcompiler 0.22.0 (branch `feat/register-substrate-slot`) registers two entries, both with `enabled: false`: `apps/formsubstrate.json` (`nodemode-dev/formsubstrate`, catalogue id `formsubstrate`) and `apps/formslot.json` (`nodemode-dev/formslot`, catalogue id `formslot`). `ids --check` compares every registry entry, enabled or not, so once that branch is merged the hourly build stops unless this file has both rows. Each row follows the rule the other rows follow: `app` is the registry's `app`, `repo` the repository's name, `catalog` the registry's `catalog.id`, and `site` the catalogue id. A disabled entry still has its row here (formpublisher's is one), and the spec still leaves it out until it is switched on, so neither app appears in `family.json` yet. When one is switched on and its repository is still private, the spec carries only its id with `public: false`.

The order of the merges matters as it did for FormMorpheus: formcompiler 0.22.0 first, then this right after. Until both are merged, the hourly build stops and the published spec stays as it was.

Run 2026-11-22: `registry.py ids --check` against the formcompiler checkout on `feat/register-substrate-slot` gave "35 registry entries, in step". Against an extract of formcompiler's `origin/main` it named `formslot` and `formsubstrate` as "in spec/ids.json, not in the registry" (rc 1), as expected until that merge. The suite: 87 passed.

### ids.json · the 33rd row, FormMorpheus; no SubForm to rename
- refers-to: spec/ids.json; tests/test_sources.py :: test_ids_file_pairs_every_registry_entry_once
- kind: change
- logged: v0.2.1 · 2026-11-22

The owner renamed an unreleased app, SubForm, to FormSubstrate (repository `nodemode-dev/formsubstrate`, catalogue and site id `formsubstrate`). A case-insensitive search of every tracked file found no `subform`, and formcompiler's registry has no entry under either name, so nothing here is renamed and no `formsubstrate` row is added: a row with no registry entry fails `ids --check`. It joins this file when the registry has it.

Two facts were checked against the file. FormPublisher's row was already `nodemode-dev/formpublisher`, catalogue and site id `formpublisher`. FormMorpheus (`nodemode-dev/formmorpheus`, id `formmorpheus`) was missing, and the file lists every enabled registry entry, private ones included (formCAD's row), so it gains a row. Its registry entry, `apps/formmorpheus.json`, is on formcompiler's branch `feat/register-morpheus-publisher` and not yet on formcompiler's `main`. That makes the order of the two merges matter. The build stops when this file and the registry disagree in either direction, and so does `ids --check`. Merge formcompiler's branch first and this one right after. Until both are merged, the hourly build stops and the published spec stays as it was; self-check's id step fails here only while this is merged and formcompiler's is not.

Run 2026-11-22: `registry.py ids --check` against the local formcompiler checkout on that branch gave "33 registry entries, in step". Against an extract of formcompiler's `origin/main` it gave "formmorpheus: in spec/ids.json, not in the registry" (rc 1), as expected until that merge. The suite: 87 passed.

### targets.json, propose.py, propose.yml · formai-templates, and the apps' source at their released tags beside the checkout
- refers-to: targets.json :: formai-templates; scripts/propose.py :: APP_CHECKOUTS, fetch_apps, listed_paths, body_of, main (checkouts); .github/workflows/propose.yml :: propose (steps app-token, target, reach, "The apps at their released tags"); docs/TARGETS.md; docs/OWNER_SETUP.md step 11
- kind: feature
- logged: v0.2.0 · 2026-11-21

The owner's words: templates become an optional download from a new repository, `formai-templates`, and formadaptor sends each app's new templates and demos there. That repository holds its own logic (`sources.json` names each app's template and demo paths; `scripts/collect.py` copies them, zips folders deterministically and writes `index.json`), and formadaptor holds none of it: the target entry is the one its builder named, `collect.py --apps-root ../formai-templates-apps` with `files` `apps/`, `index.json` and the kept copy `scripts/family.spec.json`. formadaptor runs it like every generator, `--check` then the write, and proposes what it changes.

The new need: `collect.py` reads the apps' own files, so it needs each app's source at its released tag on disk. The general step is one optional field, `app_checkouts`, and one subcommand, `propose.py checkouts`, which the workflow runs before `run`. The field must be `../<folder>` (one name, not `.` or `..`), so the clones sit beside the target's checkout, never inside it (the generator's `git status` stays the target's own) and never inside formadaptor's. The folder must be new: one that holds anything is refused, never emptied, so a mistaken path cannot delete anything. For each app the spec lists as `"public": true` with a `release`, it runs `git clone --depth 1 --single-branch --no-tags --branch <release.tag>` from `https://github.com/<repository>.git` into `<folder>/<repo>`, after checking that `repo` is a plain name, `repository` is `nodemode-dev/<repo>` and the tag is `v<x.y.z>`. The rules that already held are kept by construction: the spec's release is the newest stable one that is not yanked (releases.py), and a private app is an id with no repository, so it is never fetched. The clone runs with the generator's environment and `GIT_TERMINAL_PROMPT=0`: no token at all, since the repositories are public, and a clone that would need one fails instead of asking. `core.hooksPath=/dev/null` and no submodules: nothing in a clone is run, only read by the generator. `GIT_LFS_SKIP_SMUDGE=1` because no app uses LFS today (none of the 16 has an lfs line in `.gitattributes` at its newest tag) and a filter is code. `FORMADAPTOR_GIT_BASE` moves the clones, as it moves the push. Every public released app is fetched, not only those in the target's `sources.json`, because reading that file would be holding the target's logic; the generator ignores the rest. A clone that fails stops that target's job, since a missing checkout stops `collect.py` too and nothing should be proposed from part of the family; the other targets go on.

An unreachable target is a skip. The App token step and the target's checkout have `continue-on-error: true`; the step `reach` then writes one line to the summary ("not reachable (not created yet, no main, or the App is not installed on it), skipped") and the checkouts and run steps do not run. This is what makes enabling formai-templates before the repository exists safe, and it holds for every target: a missing installation was a red job and is now a line. The job's limit went from 20 to 30 minutes for the clones (16 apps' trees at their tags are about 990 MB on disk).

Large proposals: formadaptor already proposes by one commit pushed with git (`push`), not through the contents API, so binary files and many files at once need nothing new; GitHub refuses files over 100 MB, and collect.py and check.py refuse over 50 MB. The pull request body did list every changed path; a first proposal here can name hundreds, so `body_of` now lists at most 50 (`LISTED`), the kept copy first, then "and N more files". The commit and its file list are unchanged.

Run 2026-11-21 in /tmp/p71-formadaptor: each of the 16 apps in `sources.json` extracted with `git archive <newest tag> | tar -x` from the read-only clones (tags equal to the versions in formai-templates' index), a scratch clone of formai-templates beside them, and a hand-written spec with those 16 public at those tags plus one private id. `propose.py run --target formai-templates --dry-run`: "in step with the family spec, nothing to propose", rc 0, clone clean, in 26 seconds. With one template added to FormDesign's checkout (`library/ad/ad-banner-rehearsal.json`): branch `bot/formadaptor-ab8e7a8bd2` with `apps/formdesign/app.json`, the new template, `index.json` and `scripts/family.spec.json`, the copy byte for byte the spec. With a 47 MB binary demo added to FormFabric's as well, `plan` then `push` to a bare clone through `FORMADAPTOR_GIT_BASE=file://...`: the branch arrived with six files, the 47 MB file whole, commit by nodemode-ai, the token not in `.git/config`. `propose.py checkouts` against bare mirrors of formtxt and form.ext under the same base, with a spec holding those two, a private id and a public app with no release: two shallow clones at v0.38.0 and v0.10.0, nothing for the other two; into a folder that held the extracted apps, refused. Tests: 6 new, a stand-in `git` on `PATH` for the clones.

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

### ids.json · the 32nd row, formCAD, a private repository
- refers-to: spec/ids.json; tests/conftest.py :: MINI, routes
- kind: feature
- logged: v0.1.0 · 2026-11-19

formcompiler 0.16.1 registered a 32nd entry, `apps/formCAD.json`: enabled, its repository private. Its row here is the id pair and nothing else (catalogue and site id `formcad`). While the repository is private the spec carries `{"id": "formcad", "public": false}`; nothing else about it is read or written, and `spec.changes` names nothing for a private app that joins, so the run summary and a pull request title say only `registry 0.16.1`. The test fixtures gained the same thing: a registry entry with stand-in catalogue values and a 404 for its repository.

Run 2026-11-19: before the row, `registry.py ids --compiler <clone> --check` printed "formCAD: in the registry, not in spec/ids.json" (rc 1); with it, "32 registry entries, in step" (rc 0). `spec.py build` against a local fake of GitHub that replays the sample spec and answers 404 for formCAD (one visibility call for it and no other): 31 apps, 23 public, 8 private; against the earlier sample the only differences are the bare entry and `registry_version` 0.16.0 to 0.16.1, and with them the hash and the build time. The three enabled targets' generators, in temp copies, given a spec with the new private id alone: each in step, nothing written. The registry version alone moves one line in each target's output (each prints it), so the first run after 0.16.1 proposes that line and the spec copy to each target.

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

When this was written no app shipped `agents/manifest.json`; nineteen do now (see the dispatch entry below). The spec builder reads it at the release tag and, when it is missing (404), leaves the app's `manifest` block out instead of guessing counts from `form-app.json` or the registry. The owner's wording: counts are then left out rather than guessed.

The lists in the manifest are names, not numbers (`mcp.tools`, `mcp.read_only`, `mcp.approval_gated`, `dock.tabs`, each skill's `sub_skills`), so an app's own `--check` can compare them with its code and a reader can see which tool is gated; the spec carries the counts. `read_only` and `approval_gated` must be subsets of `tools`.

`problems_of` is a hand-written check of the same rules as `spec/agent-manifest.schema.json`, because the scripts use the standard library only (no jsonschema). The two must change together. `manifest.py check FILE --app NAME` is there for an app's own sync step to call. A manifest that breaks a rule, is not JSON, or answers a 4xx other than 404 gives a warning and no counts; a 5xx or no answer stops the build, as visibility does.

Run 2026-11-18: a sample formvis manifest passed `check` (rc 0) and `counts` gave 4 tools, 1 read-only, 1 gated, 1 skill with 3 sub-skills, a dock on two sides with 2 tabs, host API 1; a broken copy named four problems (unknown field, wrong app, a read-only tool not in tools, an unknown dock position) and exited 1. Against the fake server, formvis's manifest at v2.3.5 gave the counts, formcut's broken one a warning and `None`, formtray's missing one `None` with no warning.

### manifest.py · mcp.dispatch says what one dispatching tool reaches
- refers-to: scripts/manifest.py :: dispatch_problems, mcp_counts, exact; scripts/advisory.py :: dispatch_of, dispatch_moved; spec/agent-manifest.schema.json :: mcp.dispatch; spec/family.schema.json :: manifest.mcp.dispatch; docs/SPEC.md :: mcp.dispatch
- kind: feature
- logged: v0.1.0 · 2026-11-19

Two apps put most of what they offer behind one tool that takes a command or tool name: formlit (289 commands behind `run_command`, in a list of 82 tools) and formdesign (41 layout tools behind `use_tool`, in a list of 38). The manifest had nowhere to say so, so the family spec under-described both. One optional field is added to `mcp`: `dispatch`, a non-empty list of `{"tool": <name in mcp.tools>, "reaches": <whole number, at least 1>}`, one object per dispatching tool, each tool once. The name says what it is (a tool that dispatches) and `reaches` says what the number counts (commands or tools it can run that `mcp.tools` does not list). It is left out, not empty, when no tool dispatches, so every existing manifest validates unchanged and means what it meant.

`exact` gained an `optional` set so the one field can be missing while every other unknown key is still refused; the schema keeps `dispatch` out of `required`, and `problems_of` and the schema were changed together as before. `counts` copies `dispatch` into the spec's `manifest.mcp` only when the manifest has it, as the same `tool` and `reaches` pairs, so the shape of the spec does not change for any app without one: no key is added, nothing is null, and the content hash of a spec built from manifests without it is the same as before. The spec's schema allows the key. The advisory check names a dispatching tool main adds or drops and a changed `reaches`. No app's manifest was edited: each app's own sync writes the field from its own command registry (no number is typed), and the spec shows it once an app has released a manifest that carries it.

Run 2026-11-19: the checker over the nineteen `agents/manifest.json` files in the clones (form.ext, form.md, formAT, formPDF, formVFX, formcel, formcut, formdeck, formdesign, formencoder, formlit, formpath, formportal, formref, formtools, formtxt, formvis, formwav, formweb), each with `--app` its own registry name: all nineteen pass, before and after the change. A copy of formlit's with `dispatch: [{"tool": "run_command", "reaches": 289}]` passes and `counts` shows it; an empty list, an unknown tool, `reaches` 0, true or 2.5, a tool twice, a missing `reaches` and an extra key each fail with a named problem. The JSON schemas were also run through a real validator (jsonschema, outside this repository's tests): the nineteen files and the dispatch copy validate against the manifest schema, the sample family spec validates against the family schema with and without the dispatch counts.

### spec.py · family.json, its content hash, and the spec branch
- refers-to: scripts/spec.py :: build, public_app, content_hash, changes, title, fetch, publish; spec/family.schema.json; docs/SPEC.md
- kind: feature
- logged: v0.1.0 · 2026-11-18

`build` takes every enabled registry entry, sorted by catalogue id. A private one becomes `{"id", "public": false}` and nothing else: no name, summary, version or repository name, and nothing about it is read beyond the one visibility call. A public one carries the registry's catalogue fields, the repository and site ids from `spec/ids.json`, the launcher (`build.cli`, else the registry name, as formMCP's generator takes it today), `agents` from the registry, the newest release (or `null`) and, when the app has `agents/manifest.json` at that tag, its counts. Disabled entries (formpublisher) are left out entirely, as every target leaves them out today. The build stops when `spec/ids.json` is not in step with the registry, so a new app cannot reach the spec without its id pair being reviewed.

`content_sha256` is the SHA-256 of the document without `generated` and itself, keys sorted, no whitespace. The hourly run compares it with the published file's, so a rebuild that finds nothing new publishes nothing; `generated` alone never counts as a change, and the generators must not copy it, or every target's `--check` would fail every hour.

The spec branch is written through the Git data API (blob, tree, commit, ref) with the workflow's built-in token, so no credential is put into a git remote. Each new commit has the previous one as parent, so `fetch --previous-out` can read the spec before it and `propose.py` can title its pull requests from the difference. The update is still sent with `force: true`, so an owner who resets the branch by hand does not break the next run.

`changes` names, per app: joins the family, is public, is no longer public (by id only), a new version, new agent counts, other details, leaves the family; when nothing per app changed but the registry version did, that. `title` keeps the first three and counts the rest. With no earlier spec (the first publish, or a propose run whose previous file is missing) `changes` is empty and the title is `chore(family): follow the family spec`; the first test run showed that without this every app would have been named as joining the family.

Run 2026-11-18 against the fake server from the formcompiler copy: 30 enabled entries gave 23 public apps with their data and 7 bare private ids (formbench, formfabric, formnet, formpromo, formrec, formsculpt, formsurface; each object has exactly `id` and `public`). With formfabric's fixture answer changed from 404 to 200 the next build listed 24 public apps, FormFabric at 0.25.0 (0.25.1 is yanked), summary line "FormFabric is public", title `chore(family): FormFabric is public`, `changed=true` in the output file. A third build with nothing changed gave the same hash, `unchanged`, and the fallback title. `publish` then `publish` again and `fetch` against an in-process fake: the first commit had no parent and created the ref, the second had the first as parent and moved the ref, and `fetch` returned both files byte for byte.

### targets.json, propose.py · the target's own generator decides; formadaptor only proposes
- refers-to: targets.json; scripts/propose.py :: load_targets, plan, run_generator, generator_env, change_hash, propose, push; docs/TARGETS.md
- kind: feature
- logged: v0.1.0 · 2026-11-18

The family rule: a generated file is produced only by its own repository's generator. formadaptor holds no format of its own for a target's file; it runs `command --family <path> --check` in a clean checkout of the target at `main`, and only on exit 1 runs `command --family <path>` and reads `git status` for what changed. Any exit code other than 0 or 1 from `--check`, a non-zero exit from the write, a drift with no changed file, or a changed file outside the target's declared `files` (a path, or a folder ending in `/`) stops that target without proposing anything.

`command` is an argument list, never a shell string, so nothing in targets.json is interpreted by a shell. The generator runs with only `PATH`, `HOME`, `LANG`, `LC_ALL`, `TMPDIR` and `PYTHONDONTWRITEBYTECODE`: the App token minted for that target is not in its environment, and the workflow checks the target out with `persist-credentials: false`, so the generator cannot push or call the API. The contract says a generator never needs the network; it gets no credential to use one.

The branch is `<branch_prefix><first 10 hex of the change hash>`, where the change hash is the SHA-256 over each changed path and its new bytes. The same change gives the same branch, so a second run with the pull request still open proposes nothing; a different change gives a new branch, and every older open pull request from a `branch_prefix` branch of the same repository is commented "Superseded by #N", closed, and its branch deleted (a 404 or 422 on the delete means it is already gone). Pull requests from forks and from other branches are left alone. The commit is made as `nodemode-ai <mackin@nodemode.ai>`, the family's one identity, with the title as subject and the body as message.

The push sends the token as an `http.<base>/.extraheader` for that one command, so it is never written into `.git/config`. `FORMADAPTOR_GIT_BASE` (default `https://github.com`) moves the push to another address; it exists so the push could be run against a local bare repository.

A disabled target is skipped with a notice and `proposed=false`, and `matrix` leaves it out, so a disabled target can never fail a run (see the entry on form.ext and the profile target, v0.1.0 · 2026-11-19, for which targets are on).

Run 2026-11-18 on /tmp/formadaptor-target-formMCP (formMCP's committed `core/data/family.json` and a stand-in `setup/family.py` that follows the contract): `--dry-run` with the spec where FormFabric had just gone public printed branch `bot/formadaptor-4626ce56ed`, the one file `core/data/family.json` and the title `chore(family): FormFabric is public`. With an in-process fake GitHub and a bare repository at file:///tmp/formadaptor-remote, the real path pushed that branch (commit by nodemode-ai, the token absent from `.git/config`), opened pull request 9, commented on and closed the older bot pull request 7 and deleted its branch, and left the non-bot pull request 8 alone. After that branch was merged into the checkout's main, the run said "in step with the family spec, nothing to propose" and changed nothing. A stand-in that also wrote `stray.txt` was refused by name. `matrix` listed the three enabled targets; formtray said it is disabled.

### targets.json, propose.py · each target keeps the spec it was generated from
- refers-to: targets.json :: spec_copy, files; scripts/propose.py :: load_targets, plan, body_of; docs/TARGETS.md
- kind: feature
- logged: v0.1.0 · 2026-11-18

The family decided that a target keeps, in its own repository, a copy of the family spec its output was last generated from, and that its CI runs `--check` against that copy with no network. The generator rewrites the copy only when its output changes, so a spec change that changes nothing a person can see (another app's version) opens no pull request. Where the copy lives is the target's choice, declared as `spec_copy`, which must also be one of `files` so the "only declared files" rule still holds: formMCP and formskills `setup/family.spec.json`, the profile repository `scripts/family.spec.json`, form.ext `setup/family.spec.json` (its generator chose the same name as formMCP's).

In `plan`, after the generator has written: changed files that are only the copy count as nothing to propose, with a warning, since `--check` and the write disagreed and a pull request would change only a file nobody reads. When the output changed, the copy must then be byte for byte the spec given to `--family`; if it is not, the run fails naming the copy, because that pull request would fail the target's own check. A copy that was already equal (output hand-edited, spec unchanged) passes. Both files go in the one pull request, and the body marks the copy as such. The branch hash covers the copy too, so two specs that give the same output but differ elsewhere give two branches; the newer supersedes the older, which is right because its copy is newer.

formtray is no longer a target: its bundled list is the owner's dated release schedule, with dates for apps that are not public yet, and is kept by hand. Its entry is removed, not disabled.

Run 2026-11-18 in /tmp/formadaptor-b5 with a stand-in generator that writes `core/data/apps.json` and copies the spec when the list changes. Dry run: a spec where only formvis's version changed gave "in step, nothing to propose" and a clean checkout; a spec that adds an app gave branch `bot/formadaptor-5d6f8a5b3a` with both files, the copy byte-equal to the spec given; a stand-in whose `--check` always says drift and whose write only copies the spec gave the warning and "nothing to propose". Against a bare repository through `FORMADAPTOR_GIT_BASE=file://...` and a fake API on 127.0.0.1:28010: the first case pushed one commit by nodemode-ai with both files and opened the pull request (one GET, one POST); the second and third made no API call and pushed no branch. Profile's generator does not write a copy yet, so a proposal there fails by this rule rather than opening a pull request that would drop rows the owner has not decided on; the profile target is therefore disabled (next entry).

### propose.py, docs/TARGETS.md · a target's output changes only when something it shows changes
- refers-to: scripts/propose.py :: public_apps, kept_spec, plan, main; docs/TARGETS.md (the contract); docs/SPEC.md (`source`)
- kind: feature
- logged: v0.1.0 · 2026-11-19

The contract used to say a generator "may record `source.registry_version`". Three targets did (formMCP, formskills, form.ext), so formcompiler 0.16.0 to 0.16.1, which registered one private app and changed nothing any target shows, made every target's `--check` report drift: the hourly run would have opened a pull request in each, each asking for a new release of that target. That is the noise the kept-copy rule exists to prevent. The decision: a target's generated output changes only when something that target shows changes. It never carries the registry version, the spec's build time or its content hash; which spec generated it is recorded in the kept copy, which is rewritten only when the output changes. The three targets are being changed in their own repositories; nothing of theirs was touched from here.

formadaptor cannot read a target's output format, so it cannot see what a generator records. It can see the effect. `plan` reads the kept copy before the generator writes (the checkout is clean, so that is the committed copy, the spec the committed output was generated from). When the output then changes and the kept copy and the spec given hold the same public app data (`public_apps`: the `apps` entries with `public: true`, compared whole, so a private id that joins or leaves does not count), the proposal carries a `warning` and `main` puts it in the run summary and prints it as a `::warning::` line. It names the target and the files and says the generator is recording something that is not app data. It does not block: the pull request is the only way the target comes back in step, and the fix belongs in the target's generator. A kept copy that is missing or unreadable (a first run) gives no warning, since there is nothing to compare with. The spec passed as `--previous` is not used for this: the kept copy can be many specs behind the published one, and only the kept copy is the spec the committed output answers to. The same warning shows when the committed output was edited by hand or the generator itself changed with no spec change; the target's own CI fails in those cases, and the wording still points at the right file.

Run 2026-11-19 in /tmp/formadaptor-b8, `propose.py run --dry-run` with `GITHUB_STEP_SUMMARY` set, the tests' stand-in generator in a temp repository generated from a spec at registry 0.16.0 and committed. Two specs that differ only in `source.registry_version`, `generated` and `content_sha256`: "formx: in step with the family spec, nothing to propose", rc 0, checkout clean, no warning. The same stand-in changed to write the registry version into its output: both files proposed, rc 0, and the summary file held "Warning: formx: core/data/apps.json differs although this spec and the one it was generated from hold the same public app data; its generator is recording something that is not app data (docs/TARGETS.md). The proposal is not held back." With a private id added to the second spec as well: the same warning. With a public app added: both files proposed and no warning, for either stand-in. The unchanged stand-in with its committed output edited by hand and the same spec given again: the output file proposed, with the warning.

### targets.json · form.ext is on, profile is off
- refers-to: targets.json :: formext, profile; docs/TARGETS.md; docs/OWNER_SETUP.md steps 3, 6, 8; tests/test_propose.py :: test_a_disabled_target_is_a_skip_not_a_failure, test_form_ext_names_the_files_its_generator_writes
- kind: change
- logged: v0.1.0 · 2026-11-19

form.ext's generator now exists (`setup/hosts.py` on its working branch, with its own `--check` in CI and `setup/hosts.side.json` for the facts the spec does not carry). Its files are `.claude/skills/HOSTS.md`, `setup/hosts.json` and the kept copy `setup/family.spec.json`; the entry had named `HOSTS.md` and `core/data/hosts.json`, which that repository does not have. Corrected in targets.json and docs/TARGETS.md. The entry is enabled. One order matters: the generator must be on form.ext's `main` before the first run, or that one job fails (`fail-fast: false` keeps the others going).

The profile target (the organisation profile page, repository .github) is disabled. Its generator writes no kept copy and the owner has not decided which apps the page lists, so under the kept-copy rule every spec change would fail its job. It is switched on when the page's listing rule is chosen and the generator writes `scripts/family.spec.json`; docs/TARGETS.md says so in one sentence. A disabled target is a skip in both workflows: `propose.py matrix` leaves it out of the matrix (so propose.yml never starts a job for it, and a dispatch naming it skips every row), and `propose.py run --target profile` prints "disabled in targets.json, nothing to do", writes `proposed=false` and exits 0.

Run 2026-11-19 in /tmp/formadaptor-b6 on a clone of form.ext's working branch, with the sample spec (23 public apps): `propose.py run --target formext --dry-run` said "in step with the family spec, nothing to propose" and left the clone clean, so form.ext's committed files were generated from that spec. With formtray made private in the spec: branch `bot/formadaptor-1374ff4d9c`, files `.claude/skills/HOSTS.md`, `setup/hosts.json` and `setup/family.spec.json` together. With an extra public app (formbench, a copy of formcut's entry): nothing to propose, since it is not in the side file and has no `manifest.extensions`. `run --target profile` with the real targets.json: the skip, exit 0, `proposed=false`; `matrix` listed formmcp, formskills and formext.

Run the same way against clones of formMCP and formskills (both write their kept copies): with the sample spec, "in step, nothing to propose" for both. With formbench made public (formcut's entry under another id): one proposal each, branch `bot/formadaptor-2f2c473cb4` for formMCP (`core/data/family.json` and `setup/family.spec.json`) and `bot/formadaptor-7db2c7e912` for formskills (`core/data/apps.json` and `setup/family.spec.json`), the copy byte for byte the spec given. Nothing was wrong in formadaptor.

### hourly.yml · minute 33, build with a read-only token, publish in its own job
- refers-to: .github/workflows/hourly.yml :: spec, publish, propose
- kind: feature
- logged: v0.1.0 · 2026-11-18

Minute 33 because formcompiler's workflows start at 0, 15, 30, 45 and 17 and formpipe's at 47. This hourly run is the "has an app just gone public" check: the visibility call is what notices.

The rules are formcompiler's: every action pinned to a full commit SHA with its version as a trailing comment (the same pins formcompiler uses, since no other could be looked up here), no `${{ }}` inside `run:`, `contents: read` at the top and widened only for `publish`, and `persist-credentials: false` on every checkout. The fork guard `github.repository == 'nodemode-dev/formadaptor'` is on every job, with `github.ref == 'refs/heads/main'`, so a fork's copy of the schedule does nothing and a dispatch from another branch publishes nothing. In formcompiler that reason sits in a YAML comment above each guard; here it lives only in this log.

`spec` builds with the built-in token, which reads public repositories only, and hands `family.json` to `publish` as an artifact only when `content_sha256` differs from the published file's. `publish` is the one job with `contents: write`, and writes only the `spec` branch. `propose` calls propose.yml after a publish, passing the two App secrets by name rather than `secrets: inherit`. A failed proposal is retried by dispatching propose.yml by hand; the next hourly run proposes only when the spec changes again.

### advisory.py, hourly.yml · main against the released tag, reported and never acted on
- refers-to: scripts/advisory.py :: check, compare_manifests, compare_skills, skill_folders, manifest_differences; .github/workflows/hourly.yml :: spec, step "Main against the released tags (advisory)"
- kind: feature
- logged: v0.1.0 · 2026-11-18

The design follows released tags, with an advisory check against `main`. For each public app in the spec just built that has a release, it compares `agents/manifest.json` at `release.tag` with the same file on `main`, and the source of the one field the spec takes from `form-app.json`: the skill folders (folders with a `SKILL.md` directly inside the registry's `agents.skills` folder, which is what formcompiler's `agents.py collect` puts into `form-app.json`). It names what `main` adds or drops (tools, read-only and approval-gated tools, transports, skills and sub-skills, dock positions and tabs, the dock itself, the MCP server, extensions, the file itself, a file that no longer parses) in the workflow summary.

It reads the spec it is given, so it makes no release calls of its own: two contents calls and, for apps with a skills folder, two recursive tree calls per app (under 100 an hour with the built-in token, beside the build's own). A tree GitHub truncates is said to be too large rather than read in part. One app that cannot be compared is said so and the others go on. The script exits 0 whatever happens, and the step has `continue-on-error: true` and its own five-minute limit, so it can neither fail nor hold up the spec, the publish or the proposals. It proposes nothing and changes nothing.

Run 2026-11-18 in /tmp/formadaptor-b5 against a fake GitHub on 127.0.0.1:28020 serving the sample spec's 23 public apps (86 calls): FormCut "adds agents/manifest.json" (none at its tag); FormDesign "adds skill folders formdesign-export"; FormVis "adds tools crop_image; drops sub-skills of formvis-harness: export"; FormWav, whose main tree was answered truncated, "could not be compared"; the other 19 nothing. Summary file and stdout the same. With the fake stopped, every app said "could not be compared" and the exit was 0; with no family file, one warning and exit 0. actionlint v1.7.12 passed hourly.yml with the new step.

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
