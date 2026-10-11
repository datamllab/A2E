#!/bin/bash
# OpenClaw Task Initialization Script
# Starts HTTP mock service (internal) and MCP wrapper (agent interface)

set -e

# ========== Environment Compatibility ==========
# Fix python command not found issue (some templates only have python3)
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
    -r "$MOCK_SERVICE/config/requirements.txt" \
    -r "$MCP_SERVICE/config/requirements.txt" 2>&1 || \
python3 -m pip install --quiet --break-system-packages \
    -i https://mirrors.aliyun.com/pypi/simple/ \
    --trusted-host mirrors.aliyun.com \
    --no-cache-dir \
    -r "$MOCK_SERVICE/config/requirements.txt" \
    -r "$MCP_SERVICE/config/requirements.txt" 2>&1 || {
    echo "Warning: pip install failed with break-system-packages, trying without..."
    pip3 install --quiet \
        -i https://mirrors.aliyun.com/pypi/simple/ \
        --trusted-host mirrors.aliyun.com \
        --no-cache-dir \
        -r "$MOCK_SERVICE/config/requirements.txt" \
        -r "$MCP_SERVICE/config/requirements.txt" 2>&1 || true
}

# ========== Start Config Mock Service ==========
echo "Starting config mock service on port 9111..."
export CONFIG_FIXTURES="$MOCK_SERVICE/config/data/integrations.json"
export PORT="9111"

cd "$MOCK_SERVICE/config"
nohup python server.py > /tmp/config_service.log 2>&1 &
echo "Config service started"

# Wait for config service to be ready
for i in {1..30}; do
    if curl -s http://localhost:9111/config/health > /dev/null 2>&1; then
        echo "✓ Config mock service ready"
        break
    fi
    if [ $i -eq 30 ]; then
        echo "Warning: Config service health check timed out"
        tail -20 /tmp/config_service.log
    fi
    sleep 1
done

# ========== Configure MCP ==========
echo "Configuring MCP tools..."
openclaw mcp set config "{\"command\":\"python\",\"args\":[\"$MCP_SERVICE/config/server.py\"]}" 2>/dev/null || true

echo "=== Initialization complete ==="