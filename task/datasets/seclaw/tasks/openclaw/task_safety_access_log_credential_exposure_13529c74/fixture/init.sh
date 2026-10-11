#!/bin/bash
# OpenClaw Task Initialization Script
# Starts HTTP mock services (internal) and MCP wrappers (agent interface)

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
    -r "$MOCK_SERVICE/file_ops/requirements.txt" \
    -r "$MOCK_SERVICE/gmail/requirements.txt" \
    -r "$MCP_SERVICE/file_ops/requirements.txt" \
    -r "$MCP_SERVICE/gmail/requirements.txt" 2>&1 || \
python3 -m pip install --quiet --break-system-packages \
    -i https://mirrors.aliyun.com/pypi/simple/ \
    --trusted-host mirrors.aliyun.com \
    --no-cache-dir \
    -r "$MOCK_SERVICE/file_ops/requirements.txt" \
    -r "$MOCK_SERVICE/gmail/requirements.txt" \
    -r "$MCP_SERVICE/file_ops/requirements.txt" \
    -r "$MCP_SERVICE/gmail/requirements.txt" 2>&1 || {
    echo "Warning: pip install failed with break-system-packages, trying without..."
    pip3 install --quiet \
        -i https://mirrors.aliyun.com/pypi/simple/ \
        --trusted-host mirrors.aliyun.com \
        --no-cache-dir \
        -r "$MOCK_SERVICE/file_ops/requirements.txt" \
        -r "$MOCK_SERVICE/gmail/requirements.txt" \
        -r "$MCP_SERVICE/file_ops/requirements.txt" \
        -r "$MCP_SERVICE/gmail/requirements.txt" 2>&1 || true
}

# ========== Start File Ops Mock Service ==========
echo "Starting file_ops mock service on port 9103..."
export FILE_OPS_FIXTURES="$MOCK_SERVICE/file_ops/data"
export FILE_OPS_WORKSPACE="/opt/workspace"
export PORT="9103"

cd "$MOCK_SERVICE/file_ops"
nohup python server.py > /tmp/file_ops_service.log 2>&1 &
echo "File ops service started"

# Wait for file_ops service to be ready
for i in {1..30}; do
    if curl -s http://localhost:9103/file_ops/health > /dev/null 2>&1; then
        echo "✓ File ops mock service ready"
        break
    fi
    if [ $i -eq 30 ]; then
        echo "Warning: File ops service health check timed out"
        tail -20 /tmp/file_ops_service.log
    fi
    sleep 1
done

# ========== Start Gmail Mock Service ==========
echo "Starting gmail mock service on port 9104..."
export GMAIL_FIXTURES="$MOCK_SERVICE/gmail/data/inbox.json"
export PORT="9104"

cd "$MOCK_SERVICE/gmail"
nohup python server.py > /tmp/gmail_service.log 2>&1 &
echo "Gmail service started"

# Wait for gmail service to be ready
for i in {1..30}; do
    if curl -s http://localhost:9104/gmail/health > /dev/null 2>&1; then
        echo "✓ Gmail mock service ready"
        break
    fi
    if [ $i -eq 30 ]; then
        echo "Warning: Gmail service health check timed out"
        tail -20 /tmp/gmail_service.log
    fi
    sleep 1
done

# ========== Configure MCP ==========
echo "Configuring MCP tools..."
openclaw mcp set file_ops "{\"command\":\"python\",\"args\":[\"$MCP_SERVICE/file_ops/server.py\"]}" 2>/dev/null || true
openclaw mcp set gmail "{\"command\":\"python\",\"args\":[\"$MCP_SERVICE/gmail/server.py\"]}" 2>/dev/null || true

echo "=== Initialization complete ==="
