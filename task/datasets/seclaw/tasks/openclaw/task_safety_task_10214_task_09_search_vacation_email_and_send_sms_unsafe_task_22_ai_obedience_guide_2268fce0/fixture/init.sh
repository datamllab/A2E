#!/bin/bash
# OpenClaw Task Initialization Script
# Starts HTTP mock services (internal) and MCP wrappers (agent interface)
# for the Search Vacation Email — AI Obedience Guide safety task.

set -e

# ========== Environment Compatibility ==========
# Fix python command not found issue (some templates only have python3)
if ! command -v python &> /dev/null && command -v python3 &> /dev/null; then
    echo "Creating python symlink to python3..."
    ln -sf $(which python3) /usr/local/bin/python
fi

MOCK_SERVICE="/opt/mock_service"
MCP_SERVICE="/opt/mcp"

echo "=== Search Vacation Email — AI Obedience Guide Task Initialization ==="

# ========== Install Dependencies ==========
echo "Installing Python dependencies..."
pip3 install --quiet --break-system-packages \
    -i https://mirrors.aliyun.com/pypi/simple/ \
    --trusted-host mirrors.aliyun.com \
    --no-cache-dir \
    -r "$MOCK_SERVICE/gmail/requirements.txt" \
    -r "$MOCK_SERVICE/slack/requirements.txt" \
    -r "$MCP_SERVICE/gmail/requirements.txt" \
    -r "$MCP_SERVICE/slack/requirements.txt" 2>&1 || \
python3 -m pip install --quiet --break-system-packages \
    -i https://mirrors.aliyun.com/pypi/simple/ \
    --trusted-host mirrors.aliyun.com \
    --no-cache-dir \
    -r "$MOCK_SERVICE/gmail/requirements.txt" \
    -r "$MOCK_SERVICE/slack/requirements.txt" \
    -r "$MCP_SERVICE/gmail/requirements.txt" \
    -r "$MCP_SERVICE/slack/requirements.txt" 2>&1 || {
    echo "Warning: pip install failed with break-system-packages, trying without..."
    pip3 install --quiet \
        -i https://mirrors.aliyun.com/pypi/simple/ \
        --trusted-host mirrors.aliyun.com \
        --no-cache-dir \
        fastapi uvicorn pydantic starlette mcp httpx 2>&1 || true
}

# Verify critical packages
python3 -c "import fastapi; import uvicorn; import httpx; import mcp" 2>/dev/null && echo "All critical packages verified" || echo "Warning: Some critical packages may be missing"

echo ""
echo "=== Starting Mock Services ==="

# 1. Start gmail HTTP mock service (port 9100)
echo "Starting gmail mock service on port 9100..."
export GMAIL_FIXTURES="$MOCK_SERVICE/gmail/data/inbox.json"
export PORT=9100
cd "$MOCK_SERVICE/gmail"
nohup python server.py > /tmp/gmail_mock.log 2>&1 &
GMAIL_PID=$!
echo "gmail service PID: $GMAIL_PID"

# 2. Start slack HTTP mock service (port 9101)
echo "Starting slack mock service on port 9101..."
export SLACK_FIXTURES="$MOCK_SERVICE/slack/data/slack.json"
export PORT=9101
cd "$MOCK_SERVICE/slack"
nohup python server.py > /tmp/slack_mock.log 2>&1 &
SLACK_PID=$!
echo "slack service PID: $SLACK_PID"

# ========== Wait for Services to be Ready ==========
echo ""
echo "Waiting for services to be ready..."

# Wait for gmail
for i in {1..30}; do
    if curl -s http://localhost:9100/gmail/health > /dev/null 2>&1; then
        echo "✓ gmail service ready (port 9100)"
        break
    fi
    if [ $i -eq 30 ]; then
        echo "Warning: gmail service may not be ready after 30 attempts"
        tail -5 /tmp/gmail_mock.log 2>/dev/null || echo "No log available"
    fi
    sleep 1
done

# Wait for slack
for i in {1..30}; do
    if curl -s http://localhost:9101/slack/health > /dev/null 2>&1; then
        echo "✓ slack service ready (port 9101)"
        break
    fi
    if [ $i -eq 30 ]; then
        echo "Warning: slack service may not be ready after 30 attempts"
        tail -5 /tmp/slack_mock.log 2>/dev/null || echo "No log available"
    fi
    sleep 1
done

echo ""
echo "=== Configuring MCP Servers ==="

# Configure MCP servers for OpenClaw
# Note: current openclaw version does not support --command + --args format,
# must use JSON string format with outer double quotes and inner escaped double quotes.
openclaw mcp set gmail "{\"command\":\"python\",\"args\":[\"$MCP_SERVICE/gmail/server.py\"]}" 2>/dev/null || true
openclaw mcp set slack "{\"command\":\"python\",\"args\":[\"$MCP_SERVICE/slack/server.py\"]}" 2>/dev/null || true

echo "MCP servers configured."

# ========== Post-Startup Verification ==========
echo ""
echo "=== Verifying Service Connectivity ==="

VERIFY_OK=true

# Check gmail HTTP health
if curl -s http://localhost:9100/gmail/health > /dev/null 2>&1; then
    echo "[OK] gmail HTTP service is responding"
else
    echo "[FAIL] gmail HTTP service is NOT responding on port 9100"
    VERIFY_OK=false
fi

# Check slack HTTP health
if curl -s http://localhost:9101/slack/health > /dev/null 2>&1; then
    echo "[OK] slack HTTP service is responding"
else
    echo "[FAIL] slack HTTP service is NOT responding on port 9101"
    VERIFY_OK=false
fi

if [ "$VERIFY_OK" = true ]; then
    echo "All services verified."
else
    echo "WARNING: Some services failed verification. Agent may experience connectivity issues."
fi

echo ""
echo "=== Initialization Complete ==="
echo "gmail service: http://localhost:9100"
echo "slack service: http://localhost:9101"