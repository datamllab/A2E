#!/bin/bash
# OpenClaw Task Initialization Script
# Starts HTTP mock service (internal) and MCP wrapper (agent interface)
# Services: slack (9101)

set -e

# ========== Environment Compatibility ==========
# Fix python command if not exists (some templates only have python3)
if ! command -v python &> /dev/null && command -v python3 &> /dev/null; then
    echo "Creating python symlink to python3..."
    ln -sf $(which python3) /usr/local/bin/python
fi

MOCK_SERVICE="/opt/mock_service"
MCP_SERVICE="/opt/mcp"

echo "=== Task Initialization ==="

# ========== Install Dependencies ==========
echo "Installing Python dependencies..."
# Use Aliyun pip mirror, --break-system-packages for externally-managed-environment
pip3 install --quiet --break-system-packages \
    -i https://mirrors.aliyun.com/pypi/simple/ \
    --trusted-host mirrors.aliyun.com \
    --no-cache-dir \
    -r "$MOCK_SERVICE/slack/requirements.txt" \
    -r "$MCP_SERVICE/slack/requirements.txt" 2>&1 || \
python3 -m pip install --quiet --break-system-packages \
    -i https://mirrors.aliyun.com/pypi/simple/ \
    --trusted-host mirrors.aliyun.com \
    --no-cache-dir \
    -r "$MOCK_SERVICE/slack/requirements.txt" \
    -r "$MCP_SERVICE/slack/requirements.txt" 2>&1 || \
echo "Warning: pip install failed, continuing..."

# Verify critical packages with detailed diagnostics
echo "Verifying critical packages..."
for pkg in fastapi uvicorn httpx mcp; do
    if python3 -c "import $pkg" 2>/dev/null; then
        echo "  ✓ $pkg: OK"
    else
        echo "  ✗ $pkg: MISSING"
        # Try to get more detail about the import error
        python3 -c "import $pkg" 2>&1 | head -5
    fi
done

# Check MCP package version and API compatibility
echo "Checking MCP package API..."
python3 -c "
from mcp.server import Server
import inspect
# Check that the standard list_tools method exists
if hasattr(Server, 'list_tools'):
    print('  ✓ Server.list_tools decorator available')
else:
    print('  ✗ Server.list_tools decorator NOT found - checking alternatives')
    methods = [m for m in dir(Server) if 'list' in m.lower() and 'tool' in m.lower()]
    print(f'  Available list-related methods: {methods}')
    # Also check single form
    if hasattr(Server, 'list_tool'):
        print('  ! Server.list_tool (singular) found - may be non-standard API')
" 2>&1 || echo "  Warning: Could not verify MCP API"

echo ""
echo "=== Pre-flight Checks ==="

# Verify MCP server script is importable with detailed error reporting
echo "Checking MCP server script..."
if python3 -c "
import sys
sys.path.insert(0, '$MCP_SERVICE/slack')
import importlib.util
spec = importlib.util.spec_from_file_location('server', '$MCP_SERVICE/slack/server.py')
if spec is None:
    print('ERROR: Cannot load server.py')
    sys.exit(1)
mod = importlib.util.module_from_spec(spec)
spec.loader.exec_module(mod)
print('MCP server script loads successfully')
# Verify key functions exist
if hasattr(mod, 'server'):
    print('  ✓ server object exists')
if hasattr(mod, 'main'):
    print('  ✓ main function exists')
" 2>/tmp/mcp_preflight.log; then
    echo "✓ MCP server pre-flight check passed"
else
    echo "Warning: MCP server pre-flight check failed"
    cat /tmp/mcp_preflight.log 2>/dev/null || echo "No pre-flight log available"
fi

echo ""
echo "=== Starting Mock Services ==="

# 1. Start slack HTTP mock service (port 9101)
SLACK_PORT=9101
echo "Starting slack service on port $SLACK_PORT..."
export SLACK_FIXTURES="$MOCK_SERVICE/slack/data/slack.json"
cd "$MOCK_SERVICE/slack"
PORT=$SLACK_PORT nohup python server.py > /tmp/slack_mock.log 2>&1 &
SLACK_PID=$!
echo "slack service PID: $SLACK_PID"

# ========== Wait for Services to be Ready ==========
echo ""
echo "Waiting for services to be ready..."
for svc_info in "slack:$SLACK_PORT:/slack/health"; do
    svc_name=$(echo "$svc_info" | cut -d: -f1)
    svc_port=$(echo "$svc_info" | cut -d: -f2)
    svc_path=$(echo "$svc_info" | cut -d: -f3)
    for i in {1..30}; do
        if curl -s "http://localhost:$svc_port$svc_path" > /dev/null 2>&1; then
            echo "✓ $svc_name ready (port $svc_port)"
            break
        fi
        if [ $i -eq 30 ]; then
            echo "Warning: $svc_name health check timeout"
            echo "Service log:"
            cat "/tmp/${svc_name}_mock.log" 2>/dev/null || echo "No log available"
        fi
        sleep 1
    done
done

# ========== Configure MCP ==========
echo ""
echo "=== Configuring MCP Tools ==="
if command -v openclaw &> /dev/null; then
    MCP_MAX_RETRIES=5
    MCP_RETRY=0
    MCP_SUCCESS=false

    while [ $MCP_RETRY -lt $MCP_MAX_RETRIES ]; do
        MCP_RETRY=$((MCP_RETRY + 1))
        echo "MCP registration attempt $MCP_RETRY/$MCP_MAX_RETRIES..."

        # Remove any existing registration first
        openclaw mcp remove slack 2>/dev/null || true
        sleep 1

        # Set the MCP server
        openclaw mcp set slack "{\"command\":\"python3\",\"args\":[\"$MCP_SERVICE/slack/server.py\"]}" 2>/dev/null || \
        openclaw mcp set slack "{\"command\":\"python\",\"args\":[\"$MCP_SERVICE/slack/server.py\"]}" 2>/dev/null || true
        sleep 2

        # Verify MCP registration by checking openclaw mcp list
        if openclaw mcp list 2>/dev/null | grep -q "slack"; then
            echo "✓ slack MCP registered in tool list"

            # Additional validation: try to restart the MCP server to ensure it starts cleanly
            echo "Validating MCP server connectivity..."
            openclaw mcp restart slack 2>/dev/null || true
            sleep 2

            # Verify again after restart
            if openclaw mcp list 2>/dev/null | grep -q "slack"; then
                echo "✓ slack MCP server validated after restart"
                MCP_SUCCESS=true
                break
            else
                echo "Warning: MCP server lost after restart on attempt $MCP_RETRY"
            fi
        else
            echo "Warning: MCP registration verification failed on attempt $MCP_RETRY"
            # Print diagnostic info
            echo "Diagnostic: openclaw mcp list output:"
            openclaw mcp list 2>/dev/null || echo "  openclaw mcp list failed"
            sleep 2
        fi
    done

    if [ "$MCP_SUCCESS" = false ]; then
        echo "Warning: MCP registration failed after $MCP_MAX_RETRIES attempts"
        echo "Agent may not have access to Slack tools via MCP"
        echo "The agent should fall back to curl/HTTP if MCP tools are unavailable"
        echo "Diagnostic info:"
        openclaw mcp list 2>/dev/null || echo "  openclaw mcp list failed"
    fi
else
    echo "Warning: openclaw command not found, skipping MCP registration"
fi

echo ""
echo "=== Initialization Complete ==="
echo "Services:"
echo "  slack: http://localhost:$SLACK_PORT"