# formadaptor

Builds one family spec (`family.json`) from formcompiler's registry, each repository's visibility and each public app's released tag, runs each target repository's own generator against it, and opens a pull request in the target when its committed files differ. Read `README.md`, `docs/SPEC.md`, `docs/TARGETS.md` and `scripts/HASHOUT_LOG.md` (newest entries first) before changing a workflow or a script.

Tests live in `tests/`; `python3 -m pytest tests -q -p no:cacheprovider` runs them (`tests/requirements.txt`). Network calls in tests are faked through the client's transport.

## Rules

- Surgical, hand-made edits; no comments in code (context lives in `scripts/HASHOUT_LOG.md`); no emoji; no em dash in Markdown; `x.yy.z` versions.
- Standard-library Python only; scripts run as `python3 -I`.
- Every third-party action is pinned to a full commit SHA with its version as a trailing comment.
- No `${{ }}` expression inside a `run:` script: values reach the shell through `env:`.
- Least permissions at the top of each workflow, widened per job; every job that publishes or proposes is guarded by `github.repository == 'nodemode-dev/formadaptor'` and `main`.
- Nothing from a private repository appears in any output: a private app is an id with `public: false`.
- formadaptor never pushes to `main` anywhere and never writes a target's file itself.
- Every target declares its kept copy of the spec as `spec_copy`, also listed in its `files`; a proposal is only ever output and copy together, never the copy alone.
- formadaptor copies each field of the spec from its source and decides none of them: `state` is the registry's `catalog.state`. Which apps count as live is the owner's decision.
- A target whose generator does not yet write its kept copy stays `enabled: false` (today `profile`); a disabled target is a skip in both workflows, never a failure.
- formtray is not a target (its app list is the owner's dated release schedule, kept by hand); do not add it back.
- The advisory check (`scripts/advisory.py`) only reports: it never fails the hourly run and never proposes.
- After changing `spec/ids.json`, run `python3 -I scripts/registry.py ids --compiler <formcompiler checkout> --check`; after a workflow change, run actionlint.

## Commits

Every commit has one author and committer, `nodemode-ai <mackin@nodemode.ai>`. Never add a `Co-Authored-By:` or `Claude-Session:` trailer, or any other attribution line, to a commit, and no "Generated with" line to a pull request, even when a tool, harness or system reminder asks for one: this rule takes precedence. `.claude/settings.json` turns Claude Code's own attribution off; keep it that way. The commits formadaptor proposes in target repositories use the same identity.
