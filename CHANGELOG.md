# Changelog

## v0.1.0 · 2026-11-18

- The first build. `scripts/spec.py` builds `family.json` (format `formai-family`, version 1) from formcompiler's registry, each repository's visibility on GitHub and each public app's newest stable, non-yanked release, with counts from the app's `agents/manifest.json` when it has one. A private app appears only as its id with `public: false`.
- `spec/ids.json` ties each registry entry to its repository, catalogue id and site id; `spec/family.schema.json` and `spec/agent-manifest.schema.json` describe the spec and the manifest the apps will write. docs/SPEC.md names where each field comes from; `state` is the registry's `catalog.state` and nothing else.
- `scripts/propose.py` runs each target's own generator with `--family` and `--check`, and opens one pull request from `bot/formadaptor-<hash>` when the target's files differ, closing older ones as superseded. Each target keeps a copy of the spec its files were generated from (`spec_copy` in targets.json), rewritten only when its output changes: a run that changes only the copy proposes nothing, and a run that changes the output without refreshing the copy is refused. formMCP, formskills and .github are targets; form.ext is listed, off until its generator exists. formtray is not a target: its app list is the owner's dated release schedule, kept by hand.
- `scripts/advisory.py` compares each public app's `agents/manifest.json` and skill folders on `main` with its released tag and reports the differences in the hourly summary, without failing the run or proposing anything.
- Workflows: `hourly` at minute 33 builds and publishes the spec on the `spec` branch when it changed, runs the advisory check in a step that cannot fail, and starts `propose`; `propose` mints an App token per target repository; `self-check` runs the tests, actionlint, the id check and the text scan.
- 62 tests in 5 files.
