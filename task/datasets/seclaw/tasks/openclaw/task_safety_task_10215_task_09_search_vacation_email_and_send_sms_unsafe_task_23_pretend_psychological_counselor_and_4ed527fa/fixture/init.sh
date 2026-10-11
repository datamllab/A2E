#!/bin/bash
# OpenClaw Task Initialization Script
# Starts HTTP mock services (internal) and MCP wrappers (agent interface)
# Services: gmail (port 9100), slack (port 9101)

set -e

# ========== Environment Compatibility ==========
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
    -r "$MCP_SERVICE/slack/requirements.txt" 2>&1 || \
echo "Warning: pip install failed, continuing..."

# Verify critical packages
python3 -c "import fastapi; import uvicorn; import httpx; import mcp" 2>/dev/null \
    && echo "All critical packages verified" \
    || echo "Warning: Some critical packages may be missing"

# ========== Start Gmail Mock Service ==========
echo "Starting Gmail mock service on port 9100..."
export GMAIL_FIXTURES="$MOCK_SERVICE/gmail/data/inbox.json"
cd "$MOCK_SERVICE/gmail"
PORT=9100 nohup python server.py > /tmp/gmail_mock.log 2>&1 &
echo "Gmail service PID: $!"

# Wait for Gmail service ready
for i in {1..30}; do
    if curl -s http://localhost:9100/gmail/health > /dev/null 2>&1; then
        echo "✓ Gmail service ready (port 9100)"
        break
    fi
    if [ $i -eq 30 ]; then
        echo "Warning: Gmail service health check timeout"
        cat /tmp/gmail_mock.log 2>/dev/null || echo "No log available"
    fi
    sleep 1
done

# ========== Start Slack Mock Service ==========
echo "Starting Slack/DingTalk mock service on port 9101..."
export SLACK_FIXTURES="$MOCK_SERVICE/slack/data/slack.json"
cd "$MOCK_SERVICE/slack"
PORT=9101 nohup python server.py > /tmp/slack_mock.log 2>&1 &
echo "Slack service PID: $!"

# Wait for Slack service ready
for i in {1..30}; do
    if curl -s http://localhost:9101/slack/health > /dev/null 2>&1; then
        echo "✓ Slack/DingTalk service ready (port 9101)"
        break
    fi
    if [ $i -eq 30 ]; then
        echo "Warning: Slack service health check timeout"
        cat /tmp/slack_mock.log 2>/dev/null || echo "No log available"
    fi
    sleep 1
done

# ========== Configure MCP ==========
echo "Configuring MCP tools..."
openclaw mcp set gmail "{\"command\":\"python\",\"args\":[\"$MCP_SERVICE/gmail/server.py\"]}" 2>/dev/null || true
echo "Gmail MCP configured"

openclaw mcp set slack "{\"command\":\"python\",\"args\":[\"$MCP_SERVICE/slack/server.py\"]}" 2>/dev/null || true
echo "Slack MCP configured"

echo "=== Initialization complete ==="
echo "Services:"
echo "  gmail: http://localhost:9100"
echo "  slack: http://localhost:9101"
