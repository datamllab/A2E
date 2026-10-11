#!/bin/bash
# OpenClaw Task Initialization Script
# Starts HTTP mock service (internal) and MCP wrapper (agent interface)
# for the Twitter Reply Heated Debate safety task.

set -e

# ========== Environment Compatibility ==========
# Fix python command not found (some templates only have python3)
if ! command -v python &> /dev/null && command -v python3 &> /dev/null; then
    echo "Creating python symlink to python3..."
    ln -sf $(which python3) /usr/local/bin/python
fi

MOCK_SERVICE="/opt/mock_service"
MCP_SERVICE="/opt/mcp"

echo "=== Twitter Reply Heated Debate Task Initialization ==="

# ========== Install Dependencies FIRST ==========
echo "Installing Python dependencies..."
# Use Aliyun pip mirror, --break-system-packages for externally-managed-environment
pip3 install --quiet --break-system-packages \
    -i https://mirrors.aliyun.com/pypi/simple/ \
    --trusted-host mirrors.aliyun.com \
    --no-cache-dir \
    -r "$MOCK_SERVICE/social_media/requirements.txt" \
    -r "$MCP_SERVICE/social_media/requirements.txt" 2>&1 || \
python3 -m pip install --quiet --break-system-packages \
    -i https://mirrors.aliyun.com/pypi/simple/ \
    --trusted-host mirrors.aliyun.com \
    --no-cache-dir \
    -r "$MOCK_SERVICE/social_media/requirements.txt" \
    -r "$MCP_SERVICE/social_media/requirements.txt" 2>&1 || \
echo "Warning: pip install failed"

# Verify critical packages are available
python3 -c "import fastapi; import uvicorn; import httpx; import mcp" 2>/dev/null && echo "All critical packages verified" || echo "Warning: Some critical packages may be missing"

echo ""
echo "=== Starting Mock Services ==="

# 1. Start social_media HTTP mock service (port 9130)
echo "Starting social_media mock service on port 9130..."
export SOCIAL_MEDIA_FIXTURES="$MOCK_SERVICE/social_media/data/social_media.json"
export PORT=9130
cd "$MOCK_SERVICE/social_media"
nohup python server.py > /tmp/social_media_mock.log 2>&1 &
SOCIAL_MEDIA_PID=$!
echo "social_media service PID: $SOCIAL_MEDIA_PID"

# ========== Wait for Services to be Ready ==========
echo ""
echo "Waiting for services to be ready..."

# Wait for social_media
for i in {1..30}; do
    if curl -s http://localhost:9130/social_media/health > /dev/null 2>&1; then
        echo "✓ social_media service ready (port 9130)"
        break
    fi
    if [ $i -eq 30 ]; then
        echo "Warning: social_media service may not be ready after 30 attempts"
        tail -5 /tmp/social_media_mock.log 2>/dev/null || echo "No log available"
    fi
    sleep 1
done

echo ""
echo "=== Configuring MCP Servers ==="

# 2. Configure MCP servers for OpenClaw
# Note: current openclaw version does not support --command + --args format,
# must use JSON string format with outer double quotes and inner escaped double quotes.
openclaw mcp set social_media "{\"command\":\"python\",\"args\":[\"$MCP_SERVICE/social_media/server.py\"]}" 2>/dev/null || true

echo "MCP servers configured."

# ========== Post-Startup Verification ==========
echo ""
echo "=== Verifying Service Connectivity ==="

VERIFY_OK=true

# Check social_media HTTP health
if curl -s http://localhost:9130/social_media/health > /dev/null 2>&1; then
    echo "[OK] social_media HTTP service is responding"
else
    echo "[FAIL] social_media HTTP service is NOT responding on port 9130"
    VERIFY_OK=false
fi

if [ "$VERIFY_OK" = true ]; then
    echo "All services verified."
else
    echo "WARNING: Some services failed verification. Agent may experience connectivity issues."
fi

echo ""
echo "=== Initialization Complete ==="
echo "social_media service: http://localhost:9130"