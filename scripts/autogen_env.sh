#!/usr/bin/env bash
# Isolated AutoGen site-packages on top of the shared AEP interpreter.
# Do not uv-sync the main A2E / AEP environments.
set -euo pipefail
# shellcheck disable=SC1091
source /root/A2E/scripts/a2e_net.sh
_ISO_SITE="/root/A2E/task/agents/autogen_agentchat/.venv/lib/python3.13/site-packages"
if [ ! -d "$_ISO_SITE" ]; then
  echo "autogen isolated venv missing; create it with:" >&2
  echo "  cd /root/A2E/task/agents/autogen_agentchat && uv sync --index-strategy unsafe-best-match" >&2
  return 1 2>/dev/null || exit 1
fi
export PYTHONPATH="${_ISO_SITE}:${PYTHONPATH}"
