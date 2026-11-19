# Targets: the generator contract

A target is a repository with a file that lists the Form apps. formadaptor never writes that file itself: the target's own generator does, from `family.json` (docs/SPEC.md). Each target is declared in `targets.json`.

## The contract

A target ships one generator, run from the root of a clean checkout of its `main`:

- `[command] --family [path to family.json]` writes the target's generated files and exits 0.
- `[command] --family [path to family.json] --check` writes nothing; exits 0 when the committed files equal what it would write, and exits 1 and prints the name of each file that differs when they do not. Any other exit code is an error and nothing is proposed.

The generator:

- never needs the network and is given no token (it runs with only `PATH`, `HOME`, `LANG`, `LC_ALL`, `TMPDIR`);
- lists public apps only (`"public": true`) and writes nothing about an entry with `"public": false`;
- never copies `generated` or `content_sha256` into its output; it may record `source.registry_version`;
- is deterministic: the same `family.json` gives the same bytes;
- changes only the files declared for it in `targets.json`;
- runs its own `--check` in the target's CI against the spec it last committed (the target keeps a copy of the spec, or its CI fetches `family.json` from formadaptor's `spec` branch).

## targets.json

| Field | Meaning |
| --- | --- |
| `name` | Short name, used in the workflow and in `propose.yml`'s `target` input. |
| `repository` | `nodemode-dev/<repo>`. The App token is minted for this one repository. |
| `enabled` | `false` skips the target. |
| `command` | The generator as an argument list (no shell), for example `["python3", "-I", "setup/family.py"]`. `--family <path>` and `--check` are appended. |
| `files` | The paths the generator may change; a path ending in `/` allows any file under it. |
| `branch_prefix` | `bot/formadaptor-`. The branch is the prefix plus the first 10 hex of the SHA-256 of the changed paths and their new bytes. |

## What each target must change

| Target | File | Generator | What must change |
| --- | --- | --- | --- |
| formMCP | `core/data/family.json` | `setup/family.py` | Replace `--compiler PATH` with `--family PATH`; read `apps` from family.json, keep only `public: true` (it lists every registry entry today, private ones included); take `launcher`, `mcp` (`agents.mcp`) and `released` (`release` is not null) from the spec; record `source.registry_version` and drop `source.commit` (formcompiler's HEAD makes `--check` fail on every registry commit); print the file name on drift. Run `--check` in CI. |
| formskills | `core/data/apps.json` | `setup/apps.py` | The same as formMCP (`--family`, public only, no commit in `source`), keeping its rule of apps with a skills folder (`agents.skills` not empty); give every kind a topic, with a fallback topic for a kind not in `TOPICS`, so a new kind cannot stop the generator. Run `--check` in CI. |
| .github | `profile/README.md` | `scripts/apps_table.py` | Read `--family PATH` instead of fetching the site's catalogue (no network); keep the `state == "live"` and slug rules, using `id` and `name` of public apps; add `--check` (exit 1 naming `profile/README.md` when the blocks differ). The `apps-table.yml` workflow there can then run `--check` only, or be retired in favour of formadaptor's pull requests. |
| formtray | `core/data/apps.json` | none today (`setup/apps.py` is the name in targets.json) | A generator that keeps today's hand-written shape (categories, hue, icon, `alt_of` stay hand-kept in a side file the generator reads) and takes the app list, names and order of public apps from the spec. Enabled in targets.json once it is on main. |
| form.ext | `HOSTS.md`, `core/data/hosts.json` | none today (`setup/hosts.py`) | A generator that writes the host list and HOSTS.md from the spec's public apps that have `manifest.extensions`. Copying each host's skills from its released tag needs the skills archives, which the spec does not carry; that part stays a separate step until formadaptor passes downloaded, checksum-checked archives to the generator. Enabled once it is on main. |

formportal, formai.studio and formcompiler's README are listed in the design as later targets; they are not in targets.json yet.
