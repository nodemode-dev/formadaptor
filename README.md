# formadaptor

One family spec for the Form apps, and pull requests that keep every repository that lists the apps in step with it.

formadaptor reads formcompiler's registry, asks GitHub which app repositories are public and which release each public app last published, and writes `family.json`. It then runs each target repository's own generator against that file and opens a pull request in the target when its committed files differ. The targets are formMCP, formskills, form.ext and formai-templates (the organisation profile is listed and off); formai-templates gathers each public app's templates and demos, so before its generator runs formadaptor puts a shallow clone of each public app at its released tag beside the checkout. Each target keeps a copy of the spec its files were generated from and checks itself against it in its own CI. A target's generated files change only when something that target shows changes: they never carry the registry version, the spec's build time or its hash, so a compiler release that changes nothing a target shows proposes nothing, and a run warns when a generator records anything else. Every hour formadaptor also reports, without acting, where an app's `main` offers agents something its newest release does not. It never pushes to `main` anywhere and never runs app code.

- The spec and the agent manifest the apps write: [docs/SPEC.md](docs/SPEC.md)
- The contract each target's generator meets: [docs/TARGETS.md](docs/TARGETS.md)
- What the owner sets up: [docs/OWNER_SETUP.md](docs/OWNER_SETUP.md)

```sh
python3 -I scripts/spec.py build --compiler ../formcompiler --out family.json
python3 -I scripts/propose.py run --target formmcp --checkout ../formMCP --family family.json --dry-run
python3 -I scripts/propose.py checkouts --target formai-templates --checkout ../formai-templates --family family.json
python3 -I scripts/propose.py run --target formai-templates --checkout ../formai-templates --family family.json --dry-run
python3 -I scripts/advisory.py --family family.json
```

Version 0.2.0. Licence: GPL-3.0-only (see LICENSE and NOTICE).
