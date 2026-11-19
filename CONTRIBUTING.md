# Contributing to formadaptor

Thank you for helping. formadaptor keeps every list of the Form apps in step with one family spec.

## Where to start

- **Report what goes wrong**: the workflow run, the target and what you expected. A problem in a target's own generator belongs in that repository.
- **A new target** is the owner's decision: propose it in an issue, with the generator that meets docs/TARGETS.md.
- **A new app** is added in formcompiler's registry, not here; this repository then needs its row in `spec/ids.json`.

## Setting up

You need Python 3.11 or newer. The scripts use the standard library only; the tests need `python3 -m pip install -r tests/requirements.txt`.

| Folder | What is there |
| --- | --- |
| `.github/workflows` | hourly, propose and self-check |
| `scripts` | github_api, registry, visibility, releases, manifest, spec and propose |
| `spec` | the id pairs and the two schemas |
| `docs` | the spec, the target contract and the owner setup |
| `tests` | the test suite |

## Before you open a pull request

Run the checks CI runs (`self-check.yml`):

```sh
python3 -m pytest tests -q -p no:cacheprovider
actionlint .github/workflows/*.yml
python3 -m py_compile scripts/*.py
python3 -I scripts/registry.py ids --compiler ../formcompiler --check
```

- One change per pull request, with tests for what it adds or fixes.
- Conventional Commits, as the history: `feat(spec): ...`, `fix(propose): ...`. Leave `VERSION` and the CHANGELOG version alone; a maintainer bumps them.
- Every third-party action pinned to a full commit SHA with its version as a trailing comment; no `${{ }}` inside `run:`.

By contributing you agree that your contribution is licensed under GPL-3.0-only.
