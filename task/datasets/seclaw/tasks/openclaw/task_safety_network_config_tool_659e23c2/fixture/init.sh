#!/bin/bash
# OpenClaw Task Initialization Script
# Starts HTTP mock service (internal) and MCP wrapper (agent interface)

set -e

# ========== Environment Compatibility ==========
# Fix python command if not exists (some templates only have python3)
if ! command -v python &> /dev/null && command -v python3 &> /dev/null; then
    echo "Creating python symlink to python3..."
    ln -sf $(which python3) /usr/local/bin/python
fi

MOCK_SERVICE="/opt/mock_service"
MCP_SERVICE="/opt/mcp"
SERVICE_NAME="asb_domain"
SERVICE_PORT=9115

echo "=== Task Initialization ==="

# ========== Install Dependencies ==========
echo "Installing Python dependencies..."
INSTALL_SUCCESS=false

pip3 install --quiet --break-system-packages \
    -i https://mirrors.aliyun.com/pypi/simple/ \
    --trusted-host mirrors.aliyun.com \
    --no-cache-dir \
    -r "$MOCK_SERVICE/$SERVICE_NAME/requirements.txt" \
    -r "$MCP_SERVICE/$SERVICE_NAME/requirements.txt" 2>&1 && INSTALL_SUCCESS=true

if [ "$INSTALL_SUCCESS" = "false" ]; then
    echo "pip3 install failed, trying python3 -m pip..."
    python3 -m pip install --quiet --break-system-packages \
        -i https://mirrors.aliyun.com/pypi/simple/ \
        --trusted-host mirrors.aliyun.com \
        --no-cache-dir \
        -r "$MOCK_SERVICE/$SERVICE_NAME/requirements.txt" \
        -r "$MCP_SERVICE/$SERVICE_NAME/requirements.txt" 2>&1 && INSTALL_SUCCESS=true
fi

if [ "$INSTALL_SUCCESS" = "false" ]; then
    echo "ERROR: Failed to install Python dependencies"
    exit 1
fi

echo "✓ Dependencies installed"

# ========== Verify Critical Dependencies ==========
echo "Verifying critical dependencies..."
python3 -c "import fastapi; import uvicorn; import httpx; print('✓ Mock service dependencies verified')" || {
    echo "ERROR: Mock service dependencies (fastapi/uvicorn/httpx) not available"
    exit 1
}

python3 -c "import mcp; from mcp.server.stdio import stdio_server; print('✓ MCP dependencies verified')" || {
    echo "ERROR: MCP dependencies (mcp) not available"
    exit 1
}

echo ""
echo "=== Starting Mock Services ==="

# ========== Start asb_domain Mock Service ==========
echo "Starting $SERVICE_NAME service on port $SERVICE_PORT..."
export ASB_FIXTURES="$MOCK_SERVICE/$SERVICE_NAME/data/service_data.json"
cd "$MOCK_SERVICE/$SERVICE_NAME"
PORT=$SERVICE_PORT nohup python server.py > /tmp/asb_service.log 2>&1 &
echo "$SERVICE_NAME service PID: $!"

# ========== Wait for Mock Service to be Ready ==========
echo "Waiting for $SERVICE_NAME service to be ready..."
SERVICE_READY=false
for i in {1..30}; do
    if curl -s "http://localhost:$SERVICE_PORT/asb_domain/health" > /dev/null 2>&1; then
        echo "✓ $SERVICE_NAME service ready (port $SERVICE_PORT)"
        SERVICE_READY=true
        break
    fi
    sleep 1
done

if [ "$SERVICE_READY" = "false" ]; then
    echo "ERROR: $SERVICE_NAME service health check timeout after 30s"
    echo "Service log:"
    cat /tmp/asb_service.log 2>/dev/null || echo "No log available"
    exit 1
fi

# ========== Configure MCP ==========
echo ""
echo "=== Configuring MCP Tools ==="
if command -v openclaw &> /dev/null; then
    openclaw mcp set "$SERVICE_NAME" "{\"command\":\"python\",\"args\":[\"$MCP_SERVICE/$SERVICE_NAME/server.py\"]}" 2>/dev/null || true
    echo "✓ $SERVICE_NAME MCP configured"
else
    echo "Warning: openclaw command not found, skipping MCP registration"
fi

echo ""
echo "=== Initialization Complete ==="
echo "Services:"
echo "  $SERVICE_NAME: http://localhost:$SERVICE_PORT"