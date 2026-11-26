# Changelog

## v0.2.3 · 2026-11-25

- `spec/ids.json` gains FormCraft (`nodemode-dev/formcraft`, catalogue and site id `formcraft`) and FormRig (`nodemode-dev/formrig`, catalogue and site id `formrig`), rows 36 and 37. formcompiler's `main` registers both, and `ids --check` compares every registry entry, so the `lint` job failed on the two names and the hourly build would have stopped on them. The file now pairs all 37 registry entries.

## v0.2.2 · 2026-11-22

- `spec/ids.json` gains FormSubstrate (`nodemode-dev/formsubstrate`, catalogue and site id `formsubstrate`) and FormSlot (`nodemode-dev/formslot`, catalogue and site id `formslot`), rows 34 and 35. formcompiler 0.22.0 registers both, switched off, and `ids --check` compares every registry entry, so the hourly build would stop without them. Neither enters `family.json` while it is switched off. Merge formcompiler 0.22.0 first and this right after.

## v0.2.1 · 2026-11-22

- `spec/ids.json` gains FormMorpheus (`nodemode-dev/formmorpheus`, catalogue and site id `formmorpheus`), private until released, as the 33rd row. Its registry entry is on formcompiler's branch `feat/register-morpheus-publisher`: merge that first and this right after, since the build stops while the two disagree. FormPublisher's row already matched.
- SubForm, now FormSubstrate, was named nowhere in this repository and has no registry entry yet, so nothing was renamed; its row joins when the registry has it.

## v0.2.0 · 2026-11-21

- formai-templates is a target. It gathers every public app's templates and demos for FormPortal's optional download, with its own `scripts/collect.py --apps-root ../formai-templates-apps`; its files are `apps/`, `index.json` and the kept copy `scripts/family.spec.json`. After an app publishes a release, the next run proposes that app's new or changed templates and demos there.
- A target may declare `app_checkouts`, one new folder beside its checkout (`../<folder>`). `scripts/propose.py checkouts` fills it before the generator runs: a shallow clone of each app the spec lists as public with a release, at `release.tag`, over https with no token and hooks off; nothing in them is run, a private app is never fetched, and a folder that already holds anything is refused.
- propose.yml: a target that cannot be reached (not created yet, no `main`, or the App not installed on it) is a skip with one line in the summary, and the other targets go on. The app checkouts step runs before the generator; the job's limit is 30 minutes.
- A proposal is still one commit pushed with git, so media files (up to 50 MB each in formai-templates) and many files at once need nothing new. The pull request body names at most 50 changed files, the kept copy first.
- docs/OWNER_SETUP.md step 11: create `nodemode-dev/formai-templates`, push its `main`, add it to the App's installation. No new secret.
- 87 tests in 5 files.

## v0.1.0 · 2026-11-19

- The first build. `scripts/spec.py` builds `family.json` (format `formai-family`, version 1) from formcompiler's registry, each repository's visibility on GitHub and each public app's newest stable, non-yanked release, with counts from the app's `agents/manifest.json` when it has one. A private app appears only as its id with `public: false`.
- `spec/ids.json` ties each registry entry to its repository, catalogue id and site id; `spec/family.schema.json` and `spec/agent-manifest.schema.json` describe the spec and the manifest the apps will write. docs/SPEC.md names where each field comes from; `state` is the registry's `catalog.state` and nothing else.
- `scripts/propose.py` runs each target's own generator with `--family` and `--check`, and opens one pull request from `bot/formadaptor-<hash>` when the target's files differ, closing older ones as superseded. Each target keeps a copy of the spec its files were generated from (`spec_copy` in targets.json), rewritten only when its output changes: a run that changes only the copy proposes nothing, and a run that changes the output without refreshing the copy is refused. A target's output changes only when something that target shows changes: the contract does not let a generator record the registry version (nor the spec's build time or hash), because a compiler release that changes nothing a target shows would otherwise open a pull request in every target. When a target's output differs although its kept copy and the new spec hold the same public app data, the run summary warns, naming the target; the proposal is not held back. formMCP, formskills and form.ext are targets; the profile target (.github) is listed and off until the page's listing rule is chosen and its generator writes its copy. A disabled target is a skip, never a failure. formtray is not a target: its app list is the owner's dated release schedule, kept by hand.
- The agent manifest has one optional field, `mcp.dispatch`, for an app that puts many commands behind one tool (formlit's `run_command`, formdesign's `use_tool`): a list of `{tool, reaches}`. The spec carries it in `manifest.mcp` only when an app's manifest has it; manifests and specs without it are unchanged.
- `scripts/advisory.py` compares each public app's `agents/manifest.json` and skill folders on `main` with its released tag and reports the differences in the hourly summary, without failing the run or proposing anything.
- Workflows: `hourly` at minute 33 builds and publishes the spec on the `spec` branch when it changed, runs the advisory check in a step that cannot fail, and starts `propose`; `propose` mints an App token per target repository; `self-check` runs the tests, actionlint, the id check and the text scan.
- 81 tests in 5 files.
