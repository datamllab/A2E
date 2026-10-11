#!/bin/bash
# OpenClaw Task Initialization Script
# Starts HTTP mock service (internal) and MCP wrapper (agent interface)
# Service: todoist (port 9121)

set -e

# ========== Environment Compatibility ==========
# Fix python command not found (some templates only have python3)
if ! command -v python &> /dev/null && command -v python3 &> /dev/null; then
    echo "Creating python symlink to python3..."
    ln -sf $(which python3) /usr/local/bin/python
fi

MOCK_SERVICE="/opt/mock_service"
MCP_SERVICE="/opt/mcp"

echo "=== Task Initialization ==="

# ========== Install Dependencies ==========
echo "Installing Python dependencies..."
# Mock service dependencies
pip3 install --quiet --break-system-packages \
    -i https://mirrors.aliyun.com/pypi/simple/ \
    --trusted-host mirrors.aliyun.com \
    --no-cache-dir \
    -r "$MOCK_SERVICE/todoist/requirements.txt" 2>&1 || \
python3 -m pip install --quiet --break-system-packages \
    -i https://mirrors.aliyun.com/pypi/simple/ \
    --trusted-host mirrors.aliyun.com \
    --no-cache-dir \
    -r "$MOCK_SERVICE/todoist/requirements.txt" 2>&1 || \
echo "Warning: Todoist mock service pip install failed"

# MCP server dependencies
pip3 install --quiet --break-system-packages \
    -i https://mirrors.aliyun.com/pypi/simple/ \
    --trusted-host mirrors.aliyun.com \
    --no-cache-dir \
    -r "$MCP_SERVICE/todoist/requirements.txt" 2>&1 || \
python3 -m pip install --quiet --break-system-packages \
    -i https://mirrors.aliyun.com/pypi/simple/ \
    --trusted-host mirrors.aliyun.com \
    --no-cache-dir \
    -r "$MCP_SERVICE/todoist/requirements.txt" 2>&1 || \
echo "Warning: Todoist MCP server pip install failed"

# Verify critical packages are available
python3 -c "import fastapi; import uvicorn; import httpx; import mcp" 2>/dev/null && echo "All critical packages verified" || echo "Warning: Some critical packages may be missing"

# ========== Start Todoist Mock Service ==========
echo "Starting Todoist mock service on port 9121..."
export TODOIST_FIXTURES="$MOCK_SERVICE/todoist/data/todoist.json"
cd "$MOCK_SERVICE/todoist"
PORT=9121 nohup python server.py > /tmp/todoist_mock.log 2>&1 &
echo "Todoist service PID: $!"

# Wait for service to be ready
echo "Waiting for Todoist service..."
for i in {1..30}; do
    if curl -s http://localhost:9121/todoist/health > /dev/null 2>&1; then
        echo "Todoist service ready (port 9121)"
        break
    fi
    if [ $i -eq 30 ]; then
        echo "Warning: Todoist service health check timeout"
        cat /tmp/todoist_mock.log 2>/dev/null || echo "No log available"
    fi
    sleep 1
done

# ========== Configure MCP ==========
echo "Configuring MCP tools..."
# Note: Current openclaw version does not support --command + --args form,
# must use JSON string format with outer double quotes and inner quotes escaped.
openclaw mcp set todoist "{\"command\":\"python\",\"args\":[\"$MCP_SERVICE/todoist/server.py\"]}" 2>/dev/null || true
echo "Todoist MCP configured"

# ========== Post-Startup Verification ==========
echo ""
echo "=== Verifying Service Connectivity ==="

if curl -s http://localhost:9121/todoist/health > /dev/null 2>&1; then
    echo "[OK] Todoist HTTP service is responding"
else
    echo "[FAIL] Todoist HTTP service is NOT responding on port 9121"
fi

echo ""
echo "=== Initialization Complete ==="
echo "Todoist service: http://localhost:9121"