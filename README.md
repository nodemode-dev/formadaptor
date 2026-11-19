# formadaptor

One family spec for the Form apps, and pull requests that keep every repository that lists the apps in step with it.

formadaptor reads formcompiler's registry, asks GitHub which app repositories are public and which release each public app last published, and writes `family.json`. It then runs each target repository's own generator against that file and opens a pull request in the target when its committed files differ. It never pushes to `main` anywhere and never runs app code.

- The spec and the agent manifest the apps write: [docs/SPEC.md](docs/SPEC.md)
- The contract each target's generator meets: [docs/TARGETS.md](docs/TARGETS.md)
- What the owner sets up: [docs/OWNER_SETUP.md](docs/OWNER_SETUP.md)

```sh
python3 -I scripts/spec.py build --compiler ../formcompiler --out family.json
python3 -I scripts/propose.py run --target formmcp --checkout ../formMCP --family family.json --dry-run
```

Version 0.1.0. Licence: GPL-3.0-only (see LICENSE and NOTICE).
