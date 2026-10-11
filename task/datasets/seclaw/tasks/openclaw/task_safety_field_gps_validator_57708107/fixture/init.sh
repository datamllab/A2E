#!/bin/bash
# OpenClaw Task Initialization Script
# Starts HTTP mock service (internal) and MCP wrapper (agent interface)
# Task: field_gps_validator - DPI attack via disguised GPS validation tool

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
pip3 install --quiet --break-system-packages \
    -i https://mirrors.aliyun.com/pypi/simple/ \
    --trusted-host mirrors.aliyun.com \
    --no-cache-dir \
    -r "$MOCK_SERVICE/agriculture/requirements.txt" \
    -r "$MCP_SERVICE/agriculture/requirements.txt" 2>&1 || \
python3 -m pip install --quiet --break-system-packages \
    -i https://mirrors.aliyun.com/pypi/simple/ \
    --trusted-host mirrors.aliyun.com \
    --no-cache-dir \
    -r "$MOCK_SERVICE/agriculture/requirements.txt" \
    -r "$MCP_SERVICE/agriculture/requirements.txt" 2>&1 || \
echo "Warning: pip install failed, continuing..."

# ========== Start Agriculture Mock Service ==========
echo "Starting agriculture mock service on port 9110..."
export AGRICULTURE_FIXTURES="$MOCK_SERVICE/agriculture/data/agriculture.json"
cd "$MOCK_SERVICE/agriculture"
nohup python server.py > /tmp/agriculture_service.log 2>&1 &
echo "agriculture service started with PID $!"

# Wait for service to be ready
for i in {1..30}; do
    if curl -s http://localhost:9110/agriculture/health > /dev/null 2>&1; then
        echo "✓ agriculture service ready"
        break
    fi
    if [ $i -eq 30 ]; then
        echo "Warning: agriculture service health check timeout"
        echo "Service log:"
        cat /tmp/agriculture_service.log 2>/dev/null || echo "No log available"
    fi
    sleep 1
done

# ========== Configure MCP ==========
echo "Configuring MCP tools..."
if command -v openclaw &> /dev/null; then
    openclaw mcp set agriculture "{\"command\":\"python\",\"args\":[\"$MCP_SERVICE/agriculture/server.py\"]}" 2>/dev/null || true
    echo "✓ MCP configured"
else
    echo "Warning: openclaw command not found, skipping MCP registration"
fi

echo "=== Initialization complete ==="