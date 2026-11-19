# Owner setup

Nothing here has run on GitHub yet. In order:

1. Create the empty public repository `nodemode-dev/formadaptor`. Push `main` once, then push `feat/first-build-0.1.0` and open its pull request. Merge with a merge commit (no squash) so each commit and its signature stay.
2. Settings, Actions, General: allow GitHub Actions; Workflow permissions "Read repository contents" (the workflows widen it per job). Do not allow Actions to create or approve pull requests here; formadaptor opens them only in the targets, with the App.
3. Create a GitHub App owned by `nodemode-dev`, for example `formadaptor-bot`: no webhook; repository permissions Contents read and write, Pull requests read and write, Metadata read. Install it on the target repositories only: formMCP, formskills and .github now; formtray and form.ext when their generators land. Generate a private key and note the client ID.
4. In formadaptor: Settings, Secrets and variables, Actions: `FORMADAPTOR_APP_ID` (the client ID, `Iv...`; the numeric App ID also works) and `FORMADAPTOR_APP_PRIVATE_KEY` (the whole `.pem` file). The workflows mint a token per target repository, for that one repository.
5. In each target: if `main` has a ruleset, make sure it does not stop the App from pushing `bot/*` branches (a branch ruleset that restricts creation must list the App as a bypass actor for `bot/**`). Pull requests opened with the App token start the target's checks, unlike those opened with the built-in token.
6. Merge the target changes (docs/TARGETS.md) in formMCP, formskills and .github, each with its generated file regenerated from the current spec, so the first proposal finds nothing to change.
7. Run `hourly` by hand once (Actions, hourly, Run workflow). It creates the `spec` branch with `family.json`. Then run `propose` by hand to see every enabled target answer "in step".
8. When formtray's and form.ext's generators are on their `main`, set `"enabled": true` for them in `targets.json` (a pull request here) and install the App on those repositories.
9. formai.studio is private: the App needs access there for a site target, or the site's own CI runs the generator's `--check` against `family.json`. Not configured in 0.1.0.
10. In formcompiler's `formai-build` list of repositories it does not build, add formadaptor (it is not an app and has no registry entry).
