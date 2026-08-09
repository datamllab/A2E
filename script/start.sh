#!/usr/bin/env bash
# Install deps, build UI, and start a2e serve.
#
# Prerequisites:
#   - Python 3.10–3.14
#   - uv          https://docs.astral.sh/uv/
#   - Node.js 18+ and pnpm   https://pnpm.io/
#   - Docker      only for sandbox datasets (swe-bench, terminal-bench)
#
# Usage: bash script/start.sh

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

cd server
exec uv run a2e serve
