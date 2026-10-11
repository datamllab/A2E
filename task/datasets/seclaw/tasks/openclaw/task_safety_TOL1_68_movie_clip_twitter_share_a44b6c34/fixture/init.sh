#!/bin/bash
# OpenClaw Task Initialization Script
# Starts HTTP mock services (internal) and MCP wrappers (agent interface)
# for file_storage and social_media services

set -e

# ========== Environment compatibility ==========
# Fix missing python command (some templates only have python3)
if ! command -v python &> /dev/null && command -v python3 &> /dev/null; then
    echo "Creating python symlink to python3..."
    ln -sf $(which python3) /usr/local/bin/python
fi

MOCK_SERVICE="/opt/mock_service"
MCP_SERVICE="/opt/mcp"

echo "=== Task Initialization ==="

# ========== Install dependencies ==========
echo "Installing Python dependencies..."
# Use Alibaba Cloud pip mirror with fallback
pip3 install --quiet --break-system-packages \
    -i https://mirrors.aliyun.com/pypi/simple/ \
    --trusted-host mirrors.aliyun.com \
    --no-cache-dir \
    -r "$MOCK_SERVICE/file_storage/requirements.txt" \
    -r "$MOCK_SERVICE/social_media/requirements.txt" \
    -r "$MCP_SERVICE/file_storage/requirements.txt" \
    -r "$MCP_SERVICE/social_media/requirements.txt" 2>&1 || \
python3 -m pip install --quiet --break-system-packages \
    -i https://mirrors.aliyun.com/pypi/simple/ \
    --trusted-host mirrors.aliyun.com \
    --no-cache-dir \
    -r "$MOCK_SERVICE/file_storage/requirements.txt" \
    -r "$MOCK_SERVICE/social_media/requirements.txt" \
    -r "$MCP_SERVICE/file_storage/requirements.txt" \
    -r "$MCP_SERVICE/social_media/requirements.txt" 2>&1 || \
echo "Warning: pip install failed"

# ========== Start file_storage mock service ==========
echo "Starting file_storage mock service..."
export FILE_STORAGE_FIXTURES="$MOCK_SERVICE/file_storage/data/file_storage.json"
export PORT="9133"
cd "$MOCK_SERVICE/file_storage"
nohup python server.py > /tmp/file_storage_service.log 2>&1 &
echo "file_storage service started on port 9133"

# Wait for file_storage service ready (up to 30 seconds)
for i in {1..30}; do
    if curl -s http://localhost:9133/file_storage/health > /dev/null 2>&1; then
        echo "✓ file_storage service ready"
        break
    fi
    sleep 1
done

# ========== Start social_media mock service ==========
echo "Starting social_media mock service..."
export SOCIAL_MEDIA_FIXTURES="$MOCK_SERVICE/social_media/data/social_media.json"
export PORT="9134"
cd "$MOCK_SERVICE/social_media"
nohup python server.py > /tmp/social_media_service.log 2>&1 &
echo "social_media service started on port 9134"

# Wait for social_media service ready (up to 30 seconds)
for i in {1..30}; do
    if curl -s http://localhost:9134/social_media/health > /dev/null 2>&1; then
        echo "✓ social_media service ready"
        break
    fi
    sleep 1
done

# ========== Configure MCP ==========
echo "Configuring MCP tools..."
# Note: Current openclaw version does not support --command + --args form,
# must use JSON string format with escaped double quotes.
openclaw mcp set file_storage "{\"command\":\"python\",\"args\":[\"$MCP_SERVICE/file_storage/server.py\"]}" 2>/dev/null || true
openclaw mcp set social_media "{\"command\":\"python\",\"args\":[\"$MCP_SERVICE/social_media/server.py\"]}" 2>/dev/null || true

echo "=== Initialization complete ==="