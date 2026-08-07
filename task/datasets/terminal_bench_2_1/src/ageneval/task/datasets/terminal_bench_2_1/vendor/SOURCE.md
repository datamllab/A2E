# Vendored source

- Project: Terminal-Bench 2.1
- Repository: https://github.com/harbor-framework/terminal-bench-2-1
- Harbor dataset: `terminal-bench/terminal-bench-2-1`
- Upstream commit: `5c8eadf1f393183288fa08b8f73ca9a469cc5e00`
- Retrieved: 2026-07-24
- License: Apache-2.0

The `tasks/` directory is copied from the upstream commit without a nested Git
repository. It contains all 89 published task definitions, including
instructions, environment sources, verifier tests, and reference solutions.
The upstream leaderboard, CI configuration, and Git metadata are not part of
the dataset package.

The AEP source checkout retains two upstream environment fixtures with a `.db`
suffix. The workspace-wide `*.db` policy excludes those files from Git and
wheel artifacts. They are not used by the AEP adapter because each task runs
from its published Docker image.
