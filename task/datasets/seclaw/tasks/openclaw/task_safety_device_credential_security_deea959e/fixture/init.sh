#!/bin/bash
# OpenClaw Task Initialization Script
# Starts HTTP mock service (internal) and MCP wrapper (agent interface)

set -e

# ========== Environment Compatibility ==========
if ! command -v python &> /dev/null && command -v python3 &> /dev/null; then
    echo "Creating python symlink to python3..."
    ln -sf $(which python3) /usr/local/bin/python
fi

MOCK_SERVICE="/opt/mock_service"
MCP_SERVICE="/opt/mcp"
SERVICE_NAME="asb_domain"
SERVICE_PORT=9100

echo "=== Task Initialization ==="

# ========== Install Dependencies ==========
echo "Installing Python dependencies..."
pip3 install --quiet --break-system-packages \
    -i https://mirrors.aliyun.com/pypi/simple/ \
    --trusted-host mirrors.aliyun.com \
    --no-cache-dir \
    -r "$MOCK_SERVICE/$SERVICE_NAME/requirements.txt" \
    -r "$MCP_SERVICE/$SERVICE_NAME/requirements.txt" 2>&1 || \
python3 -m pip install --quiet --break-system-packages \
    -i https://mirrors.aliyun.com/pypi/simple/ \
    --trusted-host mirrors.aliyun.com \
    --no-cache-dir \
    -r "$MOCK_SERVICE/$SERVICE_NAME/requirements.txt" \
    -r "$MCP_SERVICE/$SERVICE_NAME/requirements.txt" 2>&1 || \
echo "Warning: pip install failed, continuing..."

# ========== Start Mock Service ==========
echo "Starting $SERVICE_NAME mock service on port $SERVICE_PORT..."
export ASB_FIXTURES="$MOCK_SERVICE/$SERVICE_NAME/data/service_fixtures.json"
export INJECTION_MODE="none"
export PORT="$SERVICE_PORT"
cd "$MOCK_SERVICE/$SERVICE_NAME"
nohup python server.py > /tmp/${SERVICE_NAME}_service.log 2>&1 &
echo "Service started with PID $!"

# Wait for service to be ready
echo "Waiting for mock service to be ready..."
for i in {1..30}; do
    if curl -s http://localhost:$SERVICE_PORT/health > /dev/null 2>&1; then
        echo "✓ Mock service ready"
        break
    fi
    if [ $i -eq 30 ]; then
        echo "Warning: Mock service health check timeout"
        echo "Service log:"
        cat /tmp/${SERVICE_NAME}_service.log 2>/dev/null || echo "No log available"
    fi
    sleep 1
done

# ========== Verify Mock Service ==========
if curl -s http://localhost:$SERVICE_PORT/health > /dev/null 2>&1; then
    echo "✓ Mock service is running"
else
    echo "Warning: Mock service may not be ready"
fi

# ========== Configure MCP ==========
echo "Configuring MCP tools..."
# Note: Current openclaw version does not support --command + --args format,
# must use JSON string format with outer double quotes and inner escaped quotes.
if command -v openclaw &> /dev/null; then
    openclaw mcp set "$SERVICE_NAME" "{\"command\":\"python\",\"args\":[\"$MCP_SERVICE/$SERVICE_NAME/server.py\"]}" 2>/dev/null || true
    echo "✓ MCP configured"
else
    echo "Warning: openclaw command not found, skipping MCP registration"
fi

echo "=== Initialization complete ==="