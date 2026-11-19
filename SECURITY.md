# Security

formadaptor reads public information and proposes pull requests in the repositories that list the Form apps. This file says what it holds and how it is guarded.

## Reporting a vulnerability

Use **Report a vulnerability** on this repository's Security tab (GitHub's private vulnerability reporting). Please do not open a public issue.

## What formadaptor holds

- A GitHub App's client ID and private key (`FORMADAPTOR_APP_ID`, `FORMADAPTOR_APP_PRIVATE_KEY`). Each run mints a token for one target repository at a time, with Contents and Pull requests write only.
- The built-in workflow token, which writes only this repository's `spec` branch.

## In scope

| Threat | What stops it |
|---|---|
| An outside pull request runs code in CI | Pull requests run only `self-check.yml`: no secret, a read-only token, `persist-credentials: false`. |
| A fork runs the hourly or propose workflows | Every job that publishes or proposes is guarded by `github.repository == 'nodemode-dev/formadaptor'` on `main` (tested in `tests/test_workflows.py`). |
| A private app reaches a public file | A private repository's app is an id with `public: false`; nothing else about it is read or written. |
| A target's generator misuses the token | The generator runs with a minimal environment and no token; the checkout keeps no credential; a change outside the target's declared files is refused. |
| A change reaches a target's main unreviewed | formadaptor only opens pull requests from `bot/formadaptor-*` branches; a person merges them. |
| A compromised action | Actions are pinned to full commit SHAs. |

## Out of scope

- A maintainer's own GitHub account being taken over.
- GitHub itself, and vulnerabilities in a target's own code (report them there).

## Supported versions

The newest release on `main`.
