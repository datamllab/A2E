#!/bin/bash
# OpenClaw Task Initialization Script
# Starts a single unified HTTP mock service (workspace_api) and MCP wrapper (workspace_tools)
# Architecture: Agent → workspace_tools MCP → workspace_api HTTP (port 9100)

# ========== Environment Compatibility ==========
if ! command -v python &> /dev/null && command -v python3 &> /dev/null; then
    echo "Creating python symlink to python3..."
    ln -sf $(which python3) /usr/local/bin/python
fi

MOCK_SERVICE="/opt/mock_service"
MCP_SERVICE="/opt/mcp"
SERVICE_PORT=9100

echo "=== Task Initialization ==="

# ========== Install Dependencies ==========
echo "Installing Python dependencies..."
pip3 install --quiet --break-system-packages \
    -i https://mirrors.aliyun.com/pypi/simple/ \
    --trusted-host mirrors.aliyun.com \
    --no-cache-dir \
    -r "$MOCK_SERVICE/workspace_api/requirements.txt" \
    -r "$MCP_SERVICE/workspace_tools/requirements.txt" 2>&1 || \
python3 -m pip install --quiet --break-system-packages \
    -i https://mirrors.aliyun.com/pypi/simple/ \
    --trusted-host mirrors.aliyun.com \
    --no-cache-dir \
    -r "$MOCK_SERVICE/workspace_api/requirements.txt" \
    -r "$MCP_SERVICE/workspace_tools/requirements.txt" 2>&1 || \
echo "Warning: pip install failed, continuing..."

# Verify critical packages
python3 -c "import fastapi; import uvicorn; import httpx; import mcp" 2>/dev/null \
    && echo "All critical packages verified" \
    || echo "Warning: Some critical packages may be missing"

# ========== Start Unified Mock Service ==========
echo ""
echo "Starting workspace_api mock service on port $SERVICE_PORT..."
export GMAIL_FIXTURES="$MOCK_SERVICE/workspace_api/data/inbox.json"
export CONFIG_FIXTURES="$MOCK_SERVICE/workspace_api/data/integrations.json"
cd "$MOCK_SERVICE/workspace_api"
PORT=$SERVICE_PORT nohup python server.py > /tmp/workspace_api_mock.log 2>&1 &
echo "workspace_api PID: $!"

# Wait for service to be ready
for i in {1..30}; do
    if curl -s "http://localhost:$SERVICE_PORT/health" > /dev/null 2>&1; then
        echo "✓ workspace_api ready (port $SERVICE_PORT)"
        break
    fi
    if [ $i -eq 30 ]; then
        echo "Warning: workspace_api health check timeout"
        echo "Service log:"
        cat /tmp/workspace_api_mock.log 2>/dev/null || echo "No log available"
    fi
    sleep 1
done

# ========== Configure MCP ==========
echo ""
echo "Configuring MCP tools..."
if command -v openclaw &> /dev/null; then
    openclaw mcp set workspace_tools "{\"command\":\"python\",\"args\":[\"$MCP_SERVICE/workspace_tools/server.py\"]}" 2>/dev/null || true
    echo "✓ workspace_tools MCP configured"
else
    echo "Warning: openclaw command not found, skipping MCP registration"
fi

echo ""
echo "=== Initialization Complete ==="
echo "Services:"
echo "  workspace_api:  http://localhost:$SERVICE_PORT"