#!/bin/bash
# OpenClaw Task Initialization Script for ASB Domain — Compliance Officer
# Starts HTTP mock service (internal) and MCP wrapper (agent interface)
#
# v3: Replaced mcp SDK dependency with a minimal JSON-RPC server that
#     implements the MCP protocol directly.  This avoids the persistent
#     "Connection closed" caused by mcp SDK version incompatibilities.
#     Added robust error handling and MCP handshake verification.

set -e

# ========== Environment compatibility ==========

if ! command -v python3 &> /dev/null; then
    echo "ERROR: python3 not found"
    exit 1
fi

# Ensure 'python' is available (some sandboxes only provide python3)
if ! command -v python &> /dev/null; then
    echo "Creating python symlink to python3..."
    ln -sf "$(which python3)" /usr/local/bin/python
fi

PYTHON_CMD="$(which python3)"

MOCK_SERVICE="/opt/mock_service"
MCP_SERVICE="/opt/mcp"

echo "=== Task Initialization ==="
echo "Python: $PYTHON_CMD ($($PYTHON_CMD --version 2>&1))"

# ========== Install dependencies ==========

echo "Installing Python dependencies..."
if ! pip3 install --quiet --break-system-packages \
    -i https://mirrors.aliyun.com/pypi/simple/ \
    --trusted-host mirrors.aliyun.com \
    --no-cache-dir \
    -r "$MOCK_SERVICE/asb_domain/requirements.txt" \
    -r "$MCP_SERVICE/asb_domain/requirements.txt" 2>&1; then
    echo "pip3 install failed, trying python3 -m pip..."
    if ! python3 -m pip install --quiet --break-system-packages \
        -i https://mirrors.aliyun.com/pypi/simple/ \
        --trusted-host mirrors.aliyun.com \
        --no-cache-dir \
        -r "$MOCK_SERVICE/asb_domain/requirements.txt" \
        -r "$MCP_SERVICE/asb_domain/requirements.txt" 2>&1; then
        echo "ERROR: pip install failed for both pip3 and python3 -m pip"
        exit 1
    fi
fi
echo "Python dependencies installed successfully"

# Verify httpx is importable (critical for MCP server)
$PYTHON_CMD -c "import httpx; print(f'httpx {httpx.__version__}')" || {
    echo "ERROR: httpx import failed"
    exit 1
}

# ========== Start mock service ==========

echo "Starting ASB domain mock service..."
export ASB_FIXTURES="$MOCK_SERVICE/asb_domain/data/service_fixtures.json"
export INJECTION_MODE="opi"
export PORT="9100"
cd "$MOCK_SERVICE/asb_domain"
nohup python server.py > /tmp/asb_domain_service.log 2>&1 &
MOCK_PID=$!
echo "Mock service started on port 9100 (PID: $MOCK_PID)"

# Wait for service ready
SERVICE_READY=false
for i in {1..30}; do
    if curl -s http://localhost:9100/health > /dev/null 2>&1; then
        echo "ASB domain mock service ready"
        SERVICE_READY=true
        break
    fi
    sleep 1
done

if [ "$SERVICE_READY" = false ]; then
    echo "ERROR: ASB domain mock service failed to start within 30 seconds"
    cat /tmp/asb_domain_service.log
    exit 1
fi

# ========== Configure MCP ==========

echo "Configuring MCP tools..."

# Use python3 explicitly in the command to avoid symlink issues
# Pass ASB_MOCK_PORT via env field so MCP server knows where to reach the mock service
MCP_SERVER_PATH="$MCP_SERVICE/asb_domain/server.py"
openclaw mcp set asb_domain "{\"command\":\"python3\",\"args\":[\"$MCP_SERVER_PATH\"],\"env\":{\"ASB_MOCK_PORT\":\"9100\"}}"

echo "MCP server registered: python3 $MCP_SERVER_PATH"

# ========== Verify MCP server ==========

echo "Verifying MCP server startup..."

# Send a full MCP initialize handshake and capture BOTH stdout and stderr.
# The minimal server writes JSON-RPC responses to stdout and logs to stderr.
INIT_REQUEST='{"jsonrpc":"2.0","id":1,"method":"initialize","params":{"protocolVersion":"2024-11-05","capabilities":{},"clientInfo":{"name":"test","version":"0.1.0"}}}'

# Use a timeout to avoid hanging if the server blocks
MCP_STDOUT="/tmp/mcp_init_stdout.txt"
MCP_STDERR="/tmp/mcp_init_stderr.txt"

echo "$INIT_REQUEST" | timeout 5 python3 "$MCP_SERVER_PATH" > "$MCP_STDOUT" 2> "$MCP_STDERR" || true

echo "--- MCP server stderr ---"
cat "$MCP_STDERR" 2>/dev/null || echo "(empty)"
echo "--- MCP server stdout ---"
cat "$MCP_STDOUT" 2>/dev/null || echo "(empty)"
echo "--- End MCP diagnostics ---"

if grep -q '"result"' "$MCP_STDOUT" 2>/dev/null; then
    echo "MCP server initialization VERIFIED"

    # Also test tools/list to ensure tool definitions are returned correctly
    TOOLS_REQUEST='{"jsonrpc":"2.0","id":2,"method":"tools/list","params":{}}'
    # Send initialize then tools/list in sequence (full handshake)
    {
        echo "$INIT_REQUEST"
        sleep 0.1
        echo '{"jsonrpc":"2.0","method":"notifications/initialized","params":{}}'
        sleep 0.1
        echo "$TOOLS_REQUEST"
    } | timeout 5 python3 "$MCP_SERVER_PATH" > /tmp/mcp_tools_stdout.txt 2>/dev/null || true

    if grep -q '"audit_manager"' /tmp/mcp_tools_stdout.txt 2>/dev/null; then
        echo "MCP tools/list VERIFIED: tool definitions returned correctly"
    else
        echo "WARNING: MCP tools/list response did not contain expected tool names"
        cat /tmp/mcp_tools_stdout.txt 2>/dev/null
    fi
else
    echo "ERROR: MCP server did not respond to initialize request"
    echo "This indicates a fundamental problem with the MCP server script."
    echo "Stderr output was:"
    cat "$MCP_STDERR" 2>/dev/null || echo "(empty)"
    # Do NOT exit -- let the task proceed so the agent can still attempt
    # to use tools.  The error diagnostic will be visible in init logs.
fi

echo "=== Initialization complete ==="