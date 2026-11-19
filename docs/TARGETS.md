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
- keeps, in the target's own repository, a copy of the family spec its output was last generated from, at the path the target chooses and declares as `spec_copy` in `targets.json` (today `setup/family.spec.json` in formMCP and formskills, `scripts/family.spec.json` in the profile repository);
- rewrites that copy, byte for byte from the file given to `--family`, only when its generated output differs from what is committed, so a change in the spec that changes nothing in its output (another app's version, say) leaves the repository as it is;
- is checked by the target's CI with `[command] --family [the copy] --check`, with no network.

formadaptor holds generators to this. When `--check` says the output differs, the files the generator then changes, its output and its copy, go into one pull request. When the generator changes only its copy, nothing a person can see has changed and nothing is proposed (the run warns). When it changes its output but leaves the copy different from the spec it was given, nothing is proposed and the run fails naming the copy, because that pull request would fail the target's own check.

## targets.json

| Field | Meaning |
| --- | --- |
| `name` | Short name, used in the workflow and in `propose.yml`'s `target` input. |
| `repository` | `nodemode-dev/<repo>`. The App token is minted for this one repository. |
| `enabled` | `false` skips the target. |
| `command` | The generator as an argument list (no shell), for example `["python3", "-I", "setup/family.py"]`. `--family <path>` and `--check` are appended. |
| `files` | The paths the generator may change, the copy of the spec included; a path ending in `/` allows any file under it. |
| `spec_copy` | The target's kept copy of the spec; must also be in `files`. |
| `branch_prefix` | `bot/formadaptor-`. The branch is the prefix plus the first 10 hex of the SHA-256 of the changed paths and their new bytes. |

## What each target must change

| Target | File | Generator | What must change |
| --- | --- | --- | --- |
| formMCP | `core/data/family.json`, copy `setup/family.spec.json` | `setup/family.py` | Met on its working branch: `--family PATH`, public apps only; `launcher`, `mcp` (`agents.mcp`) and `released` (`release` is not null) from the spec; `source.registry_version`, no `source.commit`; the file named on drift; the copy rewritten only when the output changes; CI runs `--check` against the copy. |
| formskills | `core/data/apps.json`, copy `setup/family.spec.json` | `setup/apps.py` | Met on its working branch: the same as formMCP, keeping its rule of apps with a skills folder (`agents.skills` not empty) and a topic for every kind, with a fallback for a kind it does not know. |
| .github | `profile/README.md`, copy `scripts/family.spec.json` | `scripts/apps_table.py` | Disabled in `targets.json`: it is switched on when the page's listing rule is chosen. It reads `--family PATH` and has `--check` on its working branch, but the page is kept at its published table until the owner settles which apps it lists, and no copy is committed yet, so a run here would fail by the rule above on every spec change. Still to do: keep the copy at `scripts/family.spec.json` by the rule above and point `apps-table.yml`'s `--check` at it instead of fetching the spec. The page lists apps whose `state` is `live`, and `state` is the registry's (docs/SPEC.md); which apps should show is the owner's decision, not the generator's. |
| form.ext | `.claude/skills/HOSTS.md`, `setup/hosts.json`, copy `setup/family.spec.json` | `setup/hosts.py` | Met on its working branch: it writes the host list and HOSTS.md from the spec's public apps (`manifest.extensions` from the spec where an app has it, a side file `setup/hosts.side.json` for the rest), copies the spec only when either file changes, and its CI runs `--check` against the copy. Enabled; the generator must be on form.ext's `main` before a run can find it. Copying each host's skills from its released tag needs the skills archives, which the spec does not carry; that part stays a separate step until formadaptor passes downloaded, checksum-checked archives to the generator. |

formtray is not a target: its bundled app list is the owner's dated release schedule, kept by hand, because it carries release dates for apps that are not public yet.

formportal, formai.studio and formcompiler's README are listed in the design as later targets; they are not in targets.json yet.
