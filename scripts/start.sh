#!/usr/bin/env bash
# Install deps, build UI, and start a2e serve.
#
# Prerequisites:
#   - Python 3.10–3.14
#   - uv          https://docs.astral.sh/uv/
#   - Node.js 18+ and pnpm   https://pnpm.io/
#   - Docker      only for sandbox datasets (swe-bench, terminal-bench)
#
# Usage: bash scripts/start.sh

set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$ROOT"

[[ -f .env ]] || cp .env.example .env

(cd task && uv sync --frozen --all-packages --index-strategy unsafe-best-match)
(cd server && uv sync)
(cd eval && uv sync)
(cd ui && pnpm install && pnpm build)

set -a; source .env; set +a
export no_proxy="127.0.0.1,localhost,${no_proxy:-}"
export NO_PROXY="$no_proxy"

# Keep A2E's PID files in a project-owned directory. A shared
# /tmp/.a2e-server may have been created by another user or a container and
# therefore be unwritable by the current process.
A2E_RUNTIME_TMPDIR="${A2E_RUNTIME_TMPDIR:-$ROOT/.a2e-data/tmp}"
mkdir -p "$A2E_RUNTIME_TMPDIR"
export TMPDIR="$A2E_RUNTIME_TMPDIR"

cd server
exec uv run a2e serve
