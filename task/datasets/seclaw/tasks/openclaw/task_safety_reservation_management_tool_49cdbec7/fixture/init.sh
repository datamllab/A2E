#!/bin/bash
# OpenClaw Task Initialization Script
# Starts HTTP mock service (internal) and MCP wrapper (agent interface)

set -e

# ========== Environment Compatibility ==========
# Fix python command not found (some templates only have python3)
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
# Use Aliyun pip mirror, --break-system-packages for externally-managed-environment
if ! pip3 install --quiet --break-system-packages \
    -i https://mirrors.aliyun.com/pypi/simple/ \
    --trusted-host mirrors.aliyun.com \
    --no-cache-dir \
    -r "$MOCK_SERVICE/$SERVICE_NAME/requirements.txt" \
    -r "$MCP_SERVICE/$SERVICE_NAME/requirements.txt" 2>&1; then
    if ! python3 -m pip install --quiet --break-system-packages \
        -i https://mirrors.aliyun.com/pypi/simple/ \
        --trusted-host mirrors.aliyun.com \
        --no-cache-dir \
        -r "$MOCK_SERVICE/$SERVICE_NAME/requirements.txt" \
        -r "$MCP_SERVICE/$SERVICE_NAME/requirements.txt" 2>&1; then
        echo "ERROR: pip install failed — cannot proceed without dependencies"
        exit 1
    fi
fi

# Verify critical dependencies are importable
echo "Verifying MCP dependencies..."
python3 -c "import mcp; import httpx; import anyio" || {
    echo "ERROR: Failed to import mcp, httpx, or anyio — MCP server will not start"
    exit 1
}

# ========== Start Mock Service ==========
echo "Starting mock service $SERVICE_NAME on port $SERVICE_PORT..."
export ASB_FIXTURES="$MOCK_SERVICE/$SERVICE_NAME/data/service_fixtures.json"
export INJECTION_MODE="opi"
cd "$MOCK_SERVICE/$SERVICE_NAME"
nohup python server.py > /tmp/service.log 2>&1 &
echo "Service started with PID $!"

# Wait for service to be ready
for i in $(seq 1 30); do
    if curl -s http://localhost:$SERVICE_PORT/health > /dev/null 2>&1; then
        echo "Mock service ready"
        break
    fi
    if [ $i -eq 30 ]; then
        echo "ERROR: Mock service health check timeout"
        cat /tmp/service.log 2>/dev/null || echo "No log available"
        exit 1
    fi
    sleep 1
done

# ========== Verify Mock Service Responds ==========
echo "Verifying mock service responds to tool calls..."
TOOL_RESPONSE=$(curl -s -X POST http://localhost:$SERVICE_PORT/tools/booking_manager \
    -H "Content-Type: application/json" \
    -d '{"query":"test"}' 2>&1) || {
    echo "ERROR: Mock service tool endpoint not responding"
    exit 1
}
if echo "$TOOL_RESPONSE" | grep -q "result"; then
    echo "Mock service tool endpoint verified"
else
    echo "ERROR: Mock service tool endpoint returned unexpected response: $TOOL_RESPONSE"
    exit 1
fi

# ========== Test MCP Server Standalone ==========
echo "Testing MCP server standalone..."
MCP_TEST_TIMEOUT=5
MCP_TEST_LOG="/tmp/mcp_server_test.log"
# Send MCP initialize request via stdin and check for a valid response
echo '{"jsonrpc":"2.0","id":1,"method":"initialize","params":{"protocolVersion":"2024-11-05","capabilities":{},"clientInfo":{"name":"test","version":"1.0"}}}' \
    | timeout $MCP_TEST_TIMEOUT python "$MCP_SERVICE/$SERVICE_NAME/server.py" > /tmp/mcp_init_response.json 2>$MCP_TEST_LOG || {
    echo "WARNING: MCP server standalone test failed"
    cat $MCP_TEST_LOG 2>/dev/null
    echo "Continuing with MCP registration anyway — the server may work with the framework's stdio handling"
}
if [ -f /tmp/mcp_init_response.json ] && grep -q "initialize" /tmp/mcp_init_response.json 2>/dev/null; then
    echo "MCP server standalone test passed"
fi

# ========== Configure MCP ==========
echo "Configuring MCP tools..."
if command -v openclaw &> /dev/null; then
    # Note: Current openclaw version does not support --command + --args format,
    # must use JSON string format with outer double quotes and inner quotes escaped.
    openclaw mcp set "$SERVICE_NAME" "{\"command\":\"python\",\"args\":[\"$MCP_SERVICE/$SERVICE_NAME/server.py\"]}" 2>/dev/null || true

    # Verify MCP configuration
    if openclaw mcp list 2>/dev/null | grep -q "$SERVICE_NAME"; then
        echo "MCP $SERVICE_NAME server registered successfully"
    else
        echo "ERROR: MCP $SERVICE_NAME server failed to register — task cannot proceed without tools"
        exit 1
    fi
else
    echo "Warning: openclaw command not found, skipping MCP registration"
fi

echo "=== Initialization complete ==="