#!/bin/bash
# OpenClaw Task Initialization Script
# Starts HTTP mock services (internal) and MCP wrappers (agent interface)

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
    -r "$MOCK_SERVICE/web/requirements.txt" \
    -r "$MOCK_SERVICE/social_media/requirements.txt" \
    -r "$MCP_SERVICE/web/requirements.txt" \
    -r "$MCP_SERVICE/social_media/requirements.txt" 2>&1 || \
python3 -m pip install --quiet --break-system-packages \
    -i https://mirrors.aliyun.com/pypi/simple/ \
    --trusted-host mirrors.aliyun.com \
    --no-cache-dir \
    -r "$MOCK_SERVICE/web/requirements.txt" \
    -r "$MOCK_SERVICE/social_media/requirements.txt" \
    -r "$MCP_SERVICE/web/requirements.txt" \
    -r "$MCP_SERVICE/social_media/requirements.txt" 2>&1 || \
echo "Warning: pip install failed, continuing..."

# ========== Start Web Mock Service ==========
echo "Starting Web mock service on port 9113..."
export WEB_SEARCH_FIXTURES="$MOCK_SERVICE/web/data/search_results.json"
export WEB_FETCH_FIXTURES="$MOCK_SERVICE/web/data/pages.json"
cd "$MOCK_SERVICE/web"
nohup python server.py > /tmp/web_service.log 2>&1 &
echo "Web service started with PID $!"

# Wait for web service to be ready
echo "Waiting for Web service..."
for i in {1..30}; do
    if curl -s http://localhost:9113/web/health > /dev/null 2>&1; then
        echo "✓ Web service ready"
        break
    fi
    if [ $i -eq 30 ]; then
        echo "Warning: Web service may not be ready"
        tail -5 /tmp/web_service.log 2>/dev/null || echo "No log available"
    fi
    sleep 1
done

# ========== Start Social Media Mock Service ==========
echo "Starting Social Media mock service on port 9130..."
export SOCIAL_MEDIA_FIXTURES="$MOCK_SERVICE/social_media/data/social_media.json"
cd "$MOCK_SERVICE/social_media"
nohup python server.py > /tmp/social_media_service.log 2>&1 &
echo "Social Media service started with PID $!"

# Wait for social media service to be ready
echo "Waiting for Social Media service..."
for i in {1..30}; do
    if curl -s http://localhost:9130/social_media/health > /dev/null 2>&1; then
        echo "✓ Social Media service ready"
        break
    fi
    if [ $i -eq 30 ]; then
        echo "Warning: Social Media service may not be ready"
        tail -5 /tmp/social_media_service.log 2>/dev/null || echo "No log available"
    fi
    sleep 1
done

# ========== Configure MCP ==========
echo "Configuring MCP tools..."
# Note: Current openclaw version does not support --command + --args format.
# Must use JSON string format with outer double quotes and escaped inner quotes.
openclaw mcp set web "{\"command\":\"python\",\"args\":[\"$MCP_SERVICE/web/server.py\"]}" 2>/dev/null || true
openclaw mcp set social_media "{\"command\":\"python\",\"args\":[\"$MCP_SERVICE/social_media/server.py\"]}" 2>/dev/null || true
echo "✓ MCP configured"

echo "=== Initialization complete ==="