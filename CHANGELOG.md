# Changelog

## v0.1.0 · 2026-11-18

- The first build. `scripts/spec.py` builds `family.json` (format `formai-family`, version 1) from formcompiler's registry, each repository's visibility on GitHub and each public app's newest stable, non-yanked release, with counts from the app's `agents/manifest.json` when it has one. A private app appears only as its id with `public: false`.
- `spec/ids.json` ties each registry entry to its repository, catalogue id and site id; `spec/family.schema.json` and `spec/agent-manifest.schema.json` describe the spec and the manifest the apps will write.
- `scripts/propose.py` runs each target's own generator with `--family` and `--check`, and opens one pull request from `bot/formadaptor-<hash>` when the target's files differ, closing older ones as superseded. formMCP, formskills and .github are targets; formtray and form.ext are listed, off until their generators exist.
- Workflows: `hourly` at minute 33 builds and publishes the spec on the `spec` branch when it changed and starts `propose`; `propose` mints an App token per target repository; `self-check` runs the tests, actionlint, the id check and the text scan.
- 52 tests in 4 files.
