#!/bin/bash
# SupplyManagementTool Task - Initialization Script
# Starts HTTP mock service (internal) and MCP wrapper (agent interface)

set -e

# ========== Environment compatibility ==========
# Fix python command not found (some templates only have python3)
if ! command -v python &> /dev/null && command -v python3 &> /dev/null; then
    echo "Creating python symlink to python3..."
    ln -sf $(which python3) /usr/local/bin/python
fi

MOCK_SERVICE="/opt/mock_service"
MCP_SERVICE="/opt/mcp"

echo "=== SupplyManagementTool Task Initialization ==="

# ========== Install dependencies ==========
echo "Installing Python dependencies..."
# Use Aliyun pip mirror, --break-system-packages to avoid externally-managed-environment error
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

# ========== Start HTTP Mock Service (internal, not exposed to Agent) ==========
echo "Starting internal asb_domain service..."
export ASB_FIXTURES="$MOCK_SERVICE/asb_domain/data/service_fixtures.json"
cd "$MOCK_SERVICE/asb_domain"
nohup python server.py > /tmp/asb_domain_http.log 2>&1 &
HTTP_PID=$!
echo "HTTP service PID: $HTTP_PID"

# Wait for service to be ready
echo "Waiting for HTTP service..."
for i in {1..30}; do
    if curl -s http://localhost:9100/asb/health > /dev/null 2>&1; then
        echo "✓ Service ready"
        break
    fi
    if [ $i -eq 30 ]; then
        echo "Warning: HTTP service may not be ready"
        tail -5 /tmp/asb_domain_http.log 2>/dev/null || echo "No log available"
    fi
    sleep 1
done

# ========== Configure MCP (register tools to OpenClaw) ==========
echo "Configuring MCP tools..."
# Note: Current openclaw version does not support --command + --args format,
# must use JSON string format, with outer double quotes and inner double quotes escaped.
openclaw mcp set asb_domain "{\"command\":\"python\",\"args\":[\"$MCP_SERVICE/asb_domain/server.py\"]}" 2>/dev/null || true

echo "=== Initialization complete ==="