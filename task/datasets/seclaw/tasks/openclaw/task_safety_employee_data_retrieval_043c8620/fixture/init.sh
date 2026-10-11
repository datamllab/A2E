#!/bin/bash
# OpenClaw Task Initialization Script
# Starts HTTP mock service (internal) and MCP wrapper (agent interface)

set -e

# ========== Environment Compatibility ==========
# Fix python command if only python3 exists
if ! command -v python &> /dev/null && command -v python3 &> /dev/null; then
    echo "Creating python symlink to python3..."
    ln -sf $(which python3) /usr/local/bin/python
fi

MOCK_SERVICE="/opt/mock_service"
MCP_SERVICE="/opt/mcp"
SERVICE_NAME="hrm_service"
SERVICE_PORT="9100"

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
    -r "$MCP_SERVICE/$SERVICE_NAME/requirements.txt" 2>&1 || {
    echo "Warning: pip install failed with break-system-packages, trying without..."
    pip3 install --quiet \
        -i https://mirrors.aliyun.com/pypi/simple/ \
        --trusted-host mirrors.aliyun.com \
        --no-cache-dir \
        -r "$MOCK_SERVICE/$SERVICE_NAME/requirements.txt" \
        -r "$MCP_SERVICE/$SERVICE_NAME/requirements.txt" 2>&1 || true
}

# ========== Start Mock Service ==========
echo "Starting mock service on port $SERVICE_PORT..."
export ASB_FIXTURES="$MOCK_SERVICE/$SERVICE_NAME/data/service_fixtures.json"
export INJECTION_MODE="opi"
export PORT="$SERVICE_PORT"

cd "$MOCK_SERVICE/$SERVICE_NAME"
nohup python server.py > /tmp/hrm_service.log 2>&1 &
echo $! > /tmp/hrm_service.pid
echo "Service started, PID: $(cat /tmp/hrm_service.pid)"

# Wait for service to be ready
echo "Waiting for service to be ready..."
for i in {1..30}; do
    if curl -s http://localhost:$SERVICE_PORT/hrm/health > /dev/null 2>&1; then
        echo "✓ Mock service ready"
        break
    fi
    if [ $i -eq 30 ]; then
        echo "Warning: Service health check timed out"
        tail -20 /tmp/hrm_service.log
    fi
    sleep 1
done

# ========== Configure MCP ==========
echo "Configuring MCP tools..."
# Note: Current openclaw version does not support --command + --args format,
# must use JSON string format with outer double quotes and inner quotes escaped.
openclaw mcp set "$SERVICE_NAME" "{\"command\":\"python\",\"args\":[\"$MCP_SERVICE/$SERVICE_NAME/server.py\"]}" 2>/dev/null || {
    echo "Note: openclaw MCP registration may require manual setup"
}

echo "=== Initialization complete ==="