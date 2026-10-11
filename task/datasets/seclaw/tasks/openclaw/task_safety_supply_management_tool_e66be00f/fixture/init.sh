#!/bin/bash
# OpenClaw Task Initialization Script
# Starts HTTP mock service (internal) and MCP wrapper (agent interface)

set -e

# ========== Environment compatibility ==========
if ! command -v python &> /dev/null && command -v python3 &> /dev/null; then
    echo "Creating python symlink to python3..."
    ln -sf $(which python3) /usr/local/bin/python
fi

MOCK_SERVICE="/opt/mock_service"
MCP_SERVICE="/opt/mcp"

echo "=== Task Initialization ==="

# ========== Install dependencies ==========
echo "Installing Python dependencies..."
pip3 install --quiet --break-system-packages \
    -i https://mirrors.aliyun.com/pypi/simple/ \
    --trusted-host mirrors.aliyun.com \
    --no-cache-dir \
    -r "$MOCK_SERVICE/asb_domain/requirements.txt" \
    -r "$MCP_SERVICE/asb_domain/requirements.txt" 2>&1 || \
python3 -m pip install --quiet --break-system-packages \
    -i https://mirrors.aliyun.com/pypi/simple/ \
    --trusted-host mirrors.aliyun.com \
    --no-cache-dir \
    -r "$MOCK_SERVICE/asb_domain/requirements.txt" \
    -r "$MCP_SERVICE/asb_domain/requirements.txt" 2>&1 || \
echo "Warning: pip install failed"

# ========== Start mock service ==========
echo "Starting mock service..."
export ASB_FIXTURES="$MOCK_SERVICE/asb_domain/data/service_fixtures.json"
export INJECTION_MODE="none"
cd "$MOCK_SERVICE/asb_domain"
nohup python server.py > /tmp/service.log 2>&1 &
echo "Service started"

# Wait for service readiness
for i in {1..30}; do
    if curl -s http://localhost:9100/health > /dev/null 2>&1; then
        echo "✓ Service ready"
        break
    fi
    sleep 1
done

# ========== Configure MCP ==========
echo "Configuring MCP tools..."
openclaw mcp set asb_domain "{\"command\":\"python\",\"args\":[\"$MCP_SERVICE/asb_domain/server.py\"]}" 2>/dev/null || true

echo "=== Initialization complete ==="