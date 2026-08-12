# Vendored Terminal-Bench 2.0 tasks — provenance

These task definitions are copied **verbatim** from the upstream benchmark:

- **Upstream:** https://github.com/laude-institute/terminal-bench-2
- **Commit:** `2fd12b88aafdd04a52c298e3940bcb189f9766d6` (branch `main`)
- **License:** Apache-2.0
- **Maintainer:** Laude Institute

## Why vendored

Terminal-Bench 2.0 is distributed only as a Git repository (not on PyPI or the
HuggingFace Hub), so — per AE2's standalone rule — the task definitions are copied
in rather than fetched at runtime. The per-task **Docker images**
(`alexgshaw/<task>:20251031`) are NOT vendored; they are pulled from Docker Hub on
demand, exactly like SWE-bench.

## Vendored runtime files

The upstream benchmark has **89** tasks. AE2 vendors the runtime files for all
89 tasks so the standard experiment runner can draw a random batch of 40 cases.
Each task includes `task.toml`, `instruction.md`, `environment/Dockerfile`, and
the held-out `tests/` tree. The upstream `solution/` tree and other build-context
files are not copied because AE2 runs the published task image and never reads
the oracle solution. This keeps the package smaller without changing task
loading or verification.

The loader discovers task directories automatically. Keep the Apache-2.0
attribution and the upstream `terminal-bench-canary` GUID strings intact when
updating these files.

> **Canary:** upstream files carry a `terminal-bench-canary` GUID marking them as
> benchmark data that must never enter training corpora. It is preserved verbatim.
