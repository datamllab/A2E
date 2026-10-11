#!/bin/bash
# OpenClaw Task Initialization Script
# Starts HTTP mock services (internal) and MCP wrappers (agent interface)
# Services: gmail (port 9101), smart_home (port 9120)

set -e

# ========== Environment Compatibility ==========
# Fix python command if not exists (some templates only have python3)
if ! command -v python &> /dev/null && command -v python3 &> /dev/null; then
    echo "Creating python symlink to python3..."
    ln -sf $(which python3) /usr/local/bin/python
fi

MOCK_SERVICE="/opt/mock_service"
MCP_SERVICE="/opt/mcp"

GMAIL_SERVICE="gmail"
GMAIL_PORT=9101

SMART_HOME_SERVICE="smart_home"
SMART_HOME_PORT=9120

echo "=== Task Initialization ==="

# ========== Install Dependencies ==========
echo "Installing Python dependencies..."
pip3 install --quiet --break-system-packages \
    -i https://mirrors.aliyun.com/pypi/simple/ \
    --trusted-host mirrors.aliyun.com \
    --no-cache-dir \
    -r "$MOCK_SERVICE/$GMAIL_SERVICE/requirements.txt" \
    -r "$MOCK_SERVICE/$SMART_HOME_SERVICE/requirements.txt" \
    -r "$MCP_SERVICE/$GMAIL_SERVICE/requirements.txt" \
    -r "$MCP_SERVICE/$SMART_HOME_SERVICE/requirements.txt" 2>&1 || \
python3 -m pip install --quiet --break-system-packages \
    -i https://mirrors.aliyun.com/pypi/simple/ \
    --trusted-host mirrors.aliyun.com \
    --no-cache-dir \
    -r "$MOCK_SERVICE/$GMAIL_SERVICE/requirements.txt" \
    -r "$MOCK_SERVICE/$SMART_HOME_SERVICE/requirements.txt" \
    -r "$MCP_SERVICE/$GMAIL_SERVICE/requirements.txt" \
    -r "$MCP_SERVICE/$SMART_HOME_SERVICE/requirements.txt" 2>&1 || \
echo "Warning: pip install failed, continuing..."

# ========== Start Gmail Mock Service ==========
echo "Starting gmail mock service on port $GMAIL_PORT..."
export GMAIL_FIXTURES="$MOCK_SERVICE/$GMAIL_SERVICE/data/inbox.json"
export PORT="$GMAIL_PORT"
cd "$MOCK_SERVICE/$GMAIL_SERVICE"
nohup python server.py > /tmp/gmail_service.log 2>&1 &
GMAIL_PID=$!
echo "Gmail service started with PID $GMAIL_PID"

# Wait for Gmail service to be ready
echo "Waiting for gmail service to be ready..."
for i in {1..30}; do
    if curl -s http://localhost:$GMAIL_PORT/gmail/health > /dev/null 2>&1; then
        echo "✓ Gmail service ready"
        break
    fi
    if [ $i -eq 30 ]; then
        echo "Warning: Gmail service health check timeout"
        echo "Service log:"
        cat /tmp/gmail_service.log 2>/dev/null || echo "No log available"
    fi
    sleep 1
done

# ========== Start Smart Home Mock Service ==========
echo "Starting smart_home mock service on port $SMART_HOME_PORT..."
export SMART_HOME_FIXTURES="$MOCK_SERVICE/$SMART_HOME_SERVICE/data/smart_home.json"
export PORT="$SMART_HOME_PORT"
cd "$MOCK_SERVICE/$SMART_HOME_SERVICE"
nohup python server.py > /tmp/smart_home_service.log 2>&1 &
SMART_HOME_PID=$!
echo "Smart Home service started with PID $SMART_HOME_PID"

# Wait for Smart Home service to be ready
echo "Waiting for smart_home service to be ready..."
for i in {1..30}; do
    if curl -s http://localhost:$SMART_HOME_PORT/smart-home/health > /dev/null 2>&1; then
        echo "✓ Smart Home service ready"
        break
    fi
    if [ $i -eq 30 ]; then
        echo "Warning: Smart Home service health check timeout"
        echo "Service log:"
        cat /tmp/smart_home_service.log 2>/dev/null || echo "No log available"
    fi
    sleep 1
done

# ========== Configure MCP ==========
echo "Configuring MCP tools..."
if command -v openclaw &> /dev/null; then
    openclaw mcp set "$GMAIL_SERVICE" "{\"command\":\"python\",\"args\":[\"$MCP_SERVICE/$GMAIL_SERVICE/server.py\"]}" 2>/dev/null || true
    echo "✓ Gmail MCP configured"

    openclaw mcp set "$SMART_HOME_SERVICE" "{\"command\":\"python\",\"args\":[\"$MCP_SERVICE/$SMART_HOME_SERVICE/server.py\"]}" 2>/dev/null || true
    echo "✓ Smart Home MCP configured"
else
    echo "Warning: openclaw command not found, skipping MCP registration"
fi

echo "=== Initialization complete ==="