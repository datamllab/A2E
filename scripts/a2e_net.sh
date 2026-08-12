#!/usr/bin/env bash
# A2E runtime + institutional proxy. tau_env.sh clears proxies; this restores them
# and keeps localhost / the model gateway off the proxy.
set -euo pipefail
# shellcheck disable=SC1091
source /root/A2E/scripts/tau_env.sh
source <(curl -fsSL http://deploy.i.h.pjlab.org.cn/infra/scripts/setup_proxy.sh)
: "${http_proxy:?proxy setup did not define http_proxy}"
export no_proxy="127.0.0.1,localhost,10.0.0.0/8,.pjlab.org.cn,35.220.164.252,${no_proxy:-}"
export NO_PROXY="$no_proxy"
# Allow Hub downloads now that the proxy works. Cached datasets still win.
export HF_HUB_OFFLINE="${HF_HUB_OFFLINE:-0}"
export HF_DATASETS_OFFLINE="${HF_DATASETS_OFFLINE:-0}"
export TRANSFORMERS_OFFLINE="${TRANSFORMERS_OFFLINE:-0}"
