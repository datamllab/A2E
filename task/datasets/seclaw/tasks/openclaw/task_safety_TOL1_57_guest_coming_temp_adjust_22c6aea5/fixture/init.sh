#!/bin/bash
# OpenClaw Task Initialization Script
# Starts HTTP mock service (internal) and MCP wrapper (agent interface)
# Services: smart_home (9120)

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
    -r "$MOCK_SERVICE/smart_home/requirements.txt" \
    -r "$MCP_SERVICE/smart_home/requirements.txt" 2>&1 || \
python3 -m pip install --quiet --break-system-packages \
    -i https://mirrors.aliyun.com/pypi/simple/ \
    --trusted-host mirrors.aliyun.com \
    --no-cache-dir \
    -r "$MOCK_SERVICE/smart_home/requirements.txt" \
    -r "$MCP_SERVICE/smart_home/requirements.txt" 2>&1 || \
echo "Warning: pip install failed, continuing..."

# Verify critical packages
python3 -c "import fastapi; import uvicorn; import httpx; import mcp" 2>/dev/null && echo "All critical packages verified" || echo "Warning: Some critical packages may be missing"

# ========== Verify MCP Server Module ==========
echo ""
echo "Verifying MCP server module..."
if python3 -c "import importlib.util; spec = importlib.util.spec_from_file_location('server', '$MCP_SERVICE/smart_home/server.py'); mod = importlib.util.module_from_spec(spec); spec.loader.exec_module(mod); print('MCP server module loaded OK')" 2>/dev/null; then
    echo "✓ MCP server module verified"
else
    echo "Warning: MCP server module import check failed"
fi

echo ""
echo "=== Starting Mock Services ==="

# 1. Start smart_home HTTP mock service (port 9120)
SMART_HOME_PORT=9120
echo "Starting smart_home service on port $SMART_HOME_PORT..."
export SMART_HOME_FIXTURES="$MOCK_SERVICE/smart_home/data/smart_home.json"
cd "$MOCK_SERVICE/smart_home"
PORT=$SMART_HOME_PORT nohup python server.py > /tmp/smart_home_mock.log 2>&1 &
echo "smart_home service PID: $!"

# ========== Wait for Services to be Ready ==========
echo ""
echo "Waiting for services to be ready..."
for svc_info in "smart_home:$SMART_HOME_PORT:/smart-home/health"; do
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
    if openclaw mcp set smart_home "{\"command\":\"python\",\"args\":[\"$MCP_SERVICE/smart_home/server.py\"]}" 2>&1; then
        echo "✓ smart_home MCP configured successfully"
    else
        echo "Warning: openclaw mcp set command failed for smart_home"
        # Retry once
        sleep 2
        if openclaw mcp set smart_home "{\"command\":\"python\",\"args\":[\"$MCP_SERVICE/smart_home/server.py\"]}" 2>&1; then
            echo "✓ smart_home MCP configured on retry"
        else
            echo "Error: smart_home MCP configuration failed after retry"
        fi
    fi
else
    echo "Warning: openclaw command not found, skipping MCP registration"
fi

echo ""
echo "=== Initialization Complete ==="
echo "Services:"
echo "  smart_home: http://localhost:$SMART_HOME_PORT"