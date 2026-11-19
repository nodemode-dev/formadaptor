# formadaptor

One family spec for the Form apps, and pull requests that keep every repository that lists the apps in step with it.

formadaptor reads formcompiler's registry, asks GitHub which app repositories are public and which release each public app last published, and writes `family.json`. It then runs each target repository's own generator against that file and opens a pull request in the target when its committed files differ. It never pushes to `main` anywhere and never runs app code.

Licence: GPL-3.0-only (see LICENSE and NOTICE).
