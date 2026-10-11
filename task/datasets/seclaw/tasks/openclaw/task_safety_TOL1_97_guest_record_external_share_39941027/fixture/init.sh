#!/bin/bash
# OpenClaw Task Initialization Script
# Starts HTTP mock services (internal) and MCP wrappers (agent interface)
# Services: gmail (9100), smart_home (9120)

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
# Use Aliyun pip mirror, --break-system-packages for externally-managed-environment
pip3 install --quiet --break-system-packages \
    -i https://mirrors.aliyun.com/pypi/simple/ \
    --trusted-host mirrors.aliyun.com \
    --no-cache-dir \
    -r "$MOCK_SERVICE/gmail/requirements.txt" \
    -r "$MCP_SERVICE/gmail/requirements.txt" \
    -r "$MOCK_SERVICE/smart_home/requirements.txt" \
    -r "$MCP_SERVICE/smart_home/requirements.txt" 2>&1 || \
python3 -m pip install --quiet --break-system-packages \
    -i https://mirrors.aliyun.com/pypi/simple/ \
    --trusted-host mirrors.aliyun.com \
    --no-cache-dir \
    -r "$MOCK_SERVICE/gmail/requirements.txt" \
    -r "$MCP_SERVICE/gmail/requirements.txt" \
    -r "$MOCK_SERVICE/smart_home/requirements.txt" \
    -r "$MCP_SERVICE/smart_home/requirements.txt" 2>&1 || \
echo "Warning: pip install failed, continuing..."

# Verify critical packages
python3 -c "import fastapi; import uvicorn; import httpx; import mcp" 2>/dev/null && echo "All critical packages verified" || echo "Warning: Some critical packages may be missing"

echo ""
echo "=== Starting Mock Services ==="

# 1. Start Gmail mock service (port 9100)
GMAIL_PORT=9100
echo "Starting Gmail service on port $GMAIL_PORT..."
export GMAIL_FIXTURES="$MOCK_SERVICE/gmail/data/inbox.json"
cd "$MOCK_SERVICE/gmail"
PORT=$GMAIL_PORT nohup python server.py > /tmp/gmail_mock.log 2>&1 &
echo "Gmail service PID: $!"

# Wait for Gmail service ready
for i in {1..30}; do
    if curl -s "http://localhost:$GMAIL_PORT/gmail/health" > /dev/null 2>&1; then
        echo "✓ Gmail service ready (port $GMAIL_PORT)"
        break
    fi
    if [ $i -eq 30 ]; then
        echo "Warning: Gmail service health check timeout"
        echo "Service log:"
        cat /tmp/gmail_mock.log 2>/dev/null || echo "No log available"
    fi
    sleep 1
done

# 2. Start Smart Home mock service (port 9120)
SMART_HOME_PORT=9120
echo "Starting Smart Home service on port $SMART_HOME_PORT..."
export SMART_HOME_FIXTURES="$MOCK_SERVICE/smart_home/data/smart_home.json"
cd "$MOCK_SERVICE/smart_home"
PORT=$SMART_HOME_PORT nohup python server.py > /tmp/smart_home_mock.log 2>&1 &
echo "Smart Home service PID: $!"

# Wait for Smart Home service ready
for i in {1..30}; do
    if curl -s "http://localhost:$SMART_HOME_PORT/smart-home/health" > /dev/null 2>&1; then
        echo "✓ Smart Home service ready (port $SMART_HOME_PORT)"
        break
    fi
    if [ $i -eq 30 ]; then
        echo "Warning: Smart Home service health check timeout"
        echo "Service log:"
        cat /tmp/smart_home_mock.log 2>/dev/null || echo "No log available"
    fi
    sleep 1
done

# ========== Configure MCP ==========
echo ""
echo "=== Configuring MCP Tools ==="
if command -v openclaw &> /dev/null; then
    # Note: Current openclaw version does not support --command + --args format.
    # Must use JSON string format with outer double quotes and inner escaped double quotes.
    openclaw mcp set gmail "{\"command\":\"python\",\"args\":[\"$MCP_SERVICE/gmail/server.py\"]}" 2>/dev/null || true
    echo "✓ Gmail MCP configured"
    openclaw mcp set smart_home "{\"command\":\"python\",\"args\":[\"$MCP_SERVICE/smart_home/server.py\"]}" 2>/dev/null || true
    echo "✓ Smart Home MCP configured"
else
    echo "Warning: openclaw command not found, skipping MCP registration"
fi

echo ""
echo "=== Initialization Complete ==="
echo "Services:"
echo "  Gmail:      http://localhost:$GMAIL_PORT"
echo "  Smart Home: http://localhost:$SMART_HOME_PORT"