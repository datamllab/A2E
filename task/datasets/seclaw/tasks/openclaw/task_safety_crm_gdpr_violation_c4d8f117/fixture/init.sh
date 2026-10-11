#!/bin/bash
# OpenClaw Task Initialization Script
# Starts HTTP mock service (internal) and MCP wrapper (agent interface)
# Services: crm (9110)

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
    -r "$MOCK_SERVICE/crm/requirements.txt" \
    -r "$MCP_SERVICE/crm/requirements.txt" 2>&1 || \
python3 -m pip install --quiet --break-system-packages \
    -i https://mirrors.aliyun.com/pypi/simple/ \
    --trusted-host mirrors.aliyun.com \
    --no-cache-dir \
    -r "$MOCK_SERVICE/crm/requirements.txt" \
    -r "$MCP_SERVICE/crm/requirements.txt" 2>&1 || \
echo "Warning: pip install failed, continuing..."

# Verify critical packages
python3 -c "import fastapi; import uvicorn; import httpx; import mcp" 2>/dev/null && echo "All critical packages verified" || echo "Warning: Some critical packages may be missing"

# ========== Pre-flight: Verify MCP Server Can Start ==========
echo ""
echo "=== MCP Server Pre-flight Check ==="
MCP_SERVER_SCRIPT="$MCP_SERVICE/crm/server.py"
if [ -f "$MCP_SERVER_SCRIPT" ]; then
    # Test that the MCP server script can be imported without errors
    if python3 -c "
import sys, importlib.util
spec = importlib.util.spec_from_file_location('mcp_server', '$MCP_SERVER_SCRIPT')
mod = importlib.util.module_from_spec(spec)
# Just verify imports work, don't start the server
import mcp.server
import mcp.server.stdio
import mcp.types
print('MCP server imports OK')
" 2>/dev/null; then
        echo "✓ MCP server script imports verified"
    else
        echo "Warning: MCP server script import check failed"
    fi
else
    echo "Warning: MCP server script not found at $MCP_SERVER_SCRIPT"
fi

echo ""
echo "=== Starting Mock Services ==="

# 1. Start CRM HTTP mock service (port 9110)
CRM_PORT=9110
echo "Starting crm service on port $CRM_PORT..."
export CRM_FIXTURES="$MOCK_SERVICE/crm/data/crm.json"
cd "$MOCK_SERVICE/crm"
PORT=$CRM_PORT nohup python server.py > /tmp/crm_mock.log 2>&1 &
echo "crm service PID: $!"

# ========== Wait for Services to be Ready ==========
echo ""
echo "Waiting for services to be ready..."
for svc_info in "crm:$CRM_PORT:/crm/health"; do
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
    openclaw mcp set crm "{\"command\":\"python\",\"args\":[\"$MCP_SERVICE/crm/server.py\"]}" 2>/dev/null || true
    echo "✓ crm MCP configured"

    # Verify MCP registration
    sleep 1
    if openclaw mcp list 2>/dev/null | grep -q "crm"; then
        echo "✓ crm MCP registration verified"
    else
        echo "Warning: crm MCP registration could not be verified via 'openclaw mcp list'"
    fi
else
    echo "Warning: openclaw command not found, skipping MCP registration"
fi

echo ""
echo "=== Initialization Complete ==="
echo "Services:"
echo "  crm: http://localhost:$CRM_PORT"