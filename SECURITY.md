# Security

formadaptor reads public information and proposes pull requests in the repositories that list the Form apps. This file says what it holds and how it is guarded.

## Reporting a vulnerability

Use **Report a vulnerability** on this repository's Security tab (GitHub's private vulnerability reporting). Please do not open a public issue.

## What formadaptor holds

- No secret and no App key. Pull requests in the targets are opened by formcompiler's `adaptor.yml` with formcompiler's release App, which mints a token for one target repository at a time; the scripts it runs are this repository's `scripts/propose.py plan`, `changed` and `apply`.
- The built-in workflow token, which writes only this repository's `spec` branch.

## In scope

| Threat | What stops it |
|---|---|
| An outside pull request runs code in CI | Pull requests run only `self-check.yml`: no secret, a read-only token, `persist-credentials: false`. |
| A fork runs the hourly workflow | Every job that publishes is guarded by `github.repository == 'nodemode-dev/formadaptor'` on `main` (tested in `tests/test_workflows.py`). |
| A private app reaches a public file | A private repository's app is an id with `public: false`; nothing else about it is read or written. |
| A target's generator misuses the token | The generator runs with `plan`, in a job with no secret and no environment, with a minimal environment and no token; a change outside the target's declared files is refused. The job that holds the token runs `apply`: it runs no target code and re-checks every planned file (its path against the target's files, its sha256, no link, the repository, the branch, the base commit and the change hash) before anything is pushed. |
| A change reaches a target's main unreviewed | formadaptor only opens pull requests from `bot/formadaptor-*` branches; a person merges them. |
| A compromised action | Actions are pinned to full commit SHAs. |

## Out of scope

- A maintainer's own GitHub account being taken over.
- GitHub itself, and vulnerabilities in a target's own code (report them there).

## Supported versions

The newest release on `main`.
