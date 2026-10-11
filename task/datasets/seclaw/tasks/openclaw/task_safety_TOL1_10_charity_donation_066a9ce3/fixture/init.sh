#!/bin/bash
# OpenClaw Task Initialization Script
# Starts HTTP mock service (internal) and MCP wrapper (agent interface)
# Services: crypto (9131)

set -e

# ========== Environment Compatibility ==========
# Fix python command not found issue (some templates only have python3)
if ! command -v python &> /dev/null && command -v python3 &> /dev/null; then
    echo "Creating python symlink to python3..."
    ln -sf $(which python3) /usr/local/bin/python
fi

MOCK_SERVICE="/opt/mock_service"
MCP_SERVICE="/opt/mcp"
SERVICE_NAME="crypto"
PORT="9131"

echo "=== Charity Crypto Donation CNY Task Initialization ==="

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
echo "Warning: pip install failed"

# ========== Start Mock Service ==========
echo "Starting Crypto mock service on port $PORT..."
export CRYPTO_FIXTURES="$MOCK_SERVICE/$SERVICE_NAME/data/crypto.json"
export PORT="$PORT"
cd "$MOCK_SERVICE/$SERVICE_NAME"
nohup python server.py > /tmp/crypto_mock.log 2>&1 &
MOCK_PID=$!
echo "Crypto mock service started with PID $MOCK_PID"

# Wait for service to be ready
echo "Waiting for service to be ready..."
for i in {1..30}; do
    if curl -s "http://localhost:$PORT/crypto/health" > /dev/null 2>&1; then
        echo "✓ Crypto mock service ready on port $PORT"
        break
    fi
    if [ $i -eq 30 ]; then
        echo "Warning: Service health check timed out"
        echo "Last 10 lines of log:"
        tail -10 /tmp/crypto_mock.log 2>/dev/null || echo "No log available"
    fi
    sleep 1
done

# ========== Configure MCP ==========
echo "Configuring MCP tools..."
export MOCK_SERVICE_PORT="$PORT"

MCP_SERVER_PATH="$MCP_SERVICE/$SERVICE_NAME/server.py"
if [ ! -f "$MCP_SERVER_PATH" ]; then
    echo "ERROR: MCP server not found at $MCP_SERVER_PATH"
fi

# Note: current openclaw version does not support --command + --args format,
# must use JSON string format with outer double quotes and inner escaped quotes.
MCP_RETRIES=3
MCP_RETRY_DELAY=2
MCP_REGISTERED=false

for attempt in $(seq 1 $MCP_RETRIES); do
    echo "MCP registration attempt $attempt/$MCP_RETRIES..."
    if openclaw mcp set "$SERVICE_NAME" "{\"command\":\"python\",\"args\":[\"$MCP_SERVER_PATH\"],\"env\":{\"MOCK_SERVICE_PORT\":\"$PORT\"}}" 2>&1; then
        MCP_REGISTERED=true
        echo "✓ MCP registration command succeeded"
        break
    else
        echo "MCP registration failed on attempt $attempt, retrying in ${MCP_RETRY_DELAY}s..."
        sleep $MCP_RETRY_DELAY
    fi
done

if [ "$MCP_REGISTERED" = false ]; then
    echo "Warning: MCP registration failed after $MCP_RETRIES attempts"
fi

# ========== Verify MCP Configuration ==========
echo "Verifying MCP tool configuration..."
MCP_LIST_OUTPUT=$(openclaw mcp list 2>&1 || echo "LIST_FAILED")
echo "MCP server list:"
echo "$MCP_LIST_OUTPUT" | head -20

# Check that the crypto server appears in the list
if echo "$MCP_LIST_OUTPUT" | grep -q "$SERVICE_NAME"; then
    echo "✓ MCP server '$SERVICE_NAME' found in configuration"
else
    echo "Warning: MCP server '$SERVICE_NAME' not found in configuration list"
fi

# Test MCP server startup by running a brief tool discovery
echo "Testing MCP tool discovery..."
MCP_SERVER_TEST=$(timeout 10 python -c "
import asyncio, json, sys
from mcp import ClientSession
from mcp.client.stdio import stdio_client

async def test():
    try:
        async with stdio_client(
            command='python',
            args=['$MCP_SERVER_PATH'],
            env={'MOCK_SERVICE_PORT': '$PORT'}
        ) as (read, write):
            async with ClientSession(read, write) as session:
                await session.initialize()
                tools = await session.list_tools()
                tool_names = [t.name for t in tools.tools]
                print(json.dumps(tool_names))
    except Exception as e:
        print(f'ERROR: {e}', file=sys.stderr)
        sys.exit(1)

asyncio.run(test())
" 2>/tmp/mcp_discovery.log)

if [ $? -eq 0 ] && echo "$MCP_SERVER_TEST" | grep -q "GetBalance"; then
    echo "✓ MCP tool discovery successful: $MCP_SERVER_TEST"
else
    echo "Warning: MCP tool discovery failed or incomplete"
    echo "Discovery output: $MCP_SERVER_TEST"
    echo "Discovery log:"
    cat /tmp/mcp_discovery.log 2>/dev/null || echo "No log available"
fi

echo "=== Initialization Complete ==="