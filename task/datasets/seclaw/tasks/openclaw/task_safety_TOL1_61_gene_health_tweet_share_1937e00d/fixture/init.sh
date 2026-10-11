#!/bin/bash
# OpenClaw Task Initialization Script
# Starts HTTP mock services (internal) and MCP wrappers (agent interface)
# for the gene_health_tweet_share safety task.

set -e

# ========== Environment Compatibility ==========
# Fix python command if not exists (some templates only have python3)
if ! command -v python &> /dev/null && command -v python3 &> /dev/null; then
    echo "Creating python symlink to python3..."
    ln -sf $(which python3) /usr/local/bin/python
fi

MOCK_SERVICE="/opt/mock_service"
MCP_SERVICE="/opt/mcp"

# Service configuration
GENETICS_PORT=9137
SOCIAL_MEDIA_PORT=9138

echo "=== Task Initialization ==="

# ========== Install Dependencies ==========
echo "Installing Python dependencies..."
pip3 install --quiet --break-system-packages \
    -i https://mirrors.aliyun.com/pypi/simple/ \
    --trusted-host mirrors.aliyun.com \
    --no-cache-dir \
    -r "$MOCK_SERVICE/genetics/requirements.txt" \
    -r "$MOCK_SERVICE/social_media/requirements.txt" \
    -r "$MCP_SERVICE/genetics/requirements.txt" \
    -r "$MCP_SERVICE/social_media/requirements.txt" 2>&1 || \
python3 -m pip install --quiet --break-system-packages \
    -i https://mirrors.aliyun.com/pypi/simple/ \
    --trusted-host mirrors.aliyun.com \
    --no-cache-dir \
    -r "$MOCK_SERVICE/genetics/requirements.txt" \
    -r "$MOCK_SERVICE/social_media/requirements.txt" \
    -r "$MCP_SERVICE/genetics/requirements.txt" \
    -r "$MCP_SERVICE/social_media/requirements.txt" 2>&1 || \
echo "Warning: pip install failed, continuing..."

# ========== Start Genetics Mock Service ==========
echo "Starting genetics mock service on port $GENETICS_PORT..."
export GENETICS_FIXTURES="$MOCK_SERVICE/genetics/data/genetics.json"
cd "$MOCK_SERVICE/genetics"
nohup python server.py > /tmp/genetics_service.log 2>&1 &
echo "Genetics service started with PID $!"

# Wait for genetics service to be ready
echo "Waiting for genetics service to be ready..."
for i in {1..30}; do
    if curl -s http://localhost:$GENETICS_PORT/genetics/health > /dev/null 2>&1; then
        echo "✓ Genetics service ready"
        break
    fi
    if [ $i -eq 30 ]; then
        echo "Warning: Genetics service health check timeout"
        echo "Service log:"
        cat /tmp/genetics_service.log 2>/dev/null || echo "No log available"
    fi
    sleep 1
done

# ========== Start Social Media Mock Service ==========
echo "Starting social_media mock service on port $SOCIAL_MEDIA_PORT..."
export SOCIAL_MEDIA_FIXTURES="$MOCK_SERVICE/social_media/data/social_media.json"
cd "$MOCK_SERVICE/social_media"
nohup python server.py > /tmp/social_media_service.log 2>&1 &
echo "Social media service started with PID $!"

# Wait for social media service to be ready
echo "Waiting for social_media service to be ready..."
for i in {1..30}; do
    if curl -s http://localhost:$SOCIAL_MEDIA_PORT/social_media/health > /dev/null 2>&1; then
        echo "✓ Social media service ready"
        break
    fi
    if [ $i -eq 30 ]; then
        echo "Warning: Social media service health check timeout"
        echo "Service log:"
        cat /tmp/social_media_service.log 2>/dev/null || echo "No log available"
    fi
    sleep 1
done

# ========== Configure MCP ==========
echo "Configuring MCP tools..."
if command -v openclaw &> /dev/null; then
    openclaw mcp set genetics "{\"command\":\"python\",\"args\":[\"$MCP_SERVICE/genetics/server.py\"]}" 2>/dev/null || true
    echo "✓ Genetics MCP configured"

    openclaw mcp set social_media "{\"command\":\"python\",\"args\":[\"$MCP_SERVICE/social_media/server.py\"]}" 2>/dev/null || true
    echo "✓ Social media MCP configured"
else
    echo "Warning: openclaw command not found, skipping MCP registration"
fi

echo "=== Initialization complete ==="