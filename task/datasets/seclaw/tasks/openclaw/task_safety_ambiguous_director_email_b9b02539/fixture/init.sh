#!/bin/bash
# OpenClaw Task Initialization Script
# Starts HTTP mock services (internal) and MCP wrappers (agent interface)
# Services: gmail (email), contacts (contact lookup)

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
    -r "$MOCK_SERVICE/gmail/requirements.txt" \
    -r "$MCP_SERVICE/gmail/requirements.txt" \
    -r "$MOCK_SERVICE/contacts/requirements.txt" \
    -r "$MCP_SERVICE/contacts/requirements.txt" 2>&1 || \
python3 -m pip install --quiet --break-system-packages \
    -i https://mirrors.aliyun.com/pypi/simple/ \
    --trusted-host mirrors.aliyun.com \
    --no-cache-dir \
    -r "$MOCK_SERVICE/gmail/requirements.txt" \
    -r "$MCP_SERVICE/gmail/requirements.txt" \
    -r "$MOCK_SERVICE/contacts/requirements.txt" \
    -r "$MCP_SERVICE/contacts/requirements.txt" 2>&1 || \
echo "Warning: pip install failed, continuing..."

# ========== Start Gmail Mock Service ==========
GMAIL_PORT=9100
echo "Starting gmail mock service on port $GMAIL_PORT..."
export GMAIL_FIXTURES="$MOCK_SERVICE/gmail/data"
cd "$MOCK_SERVICE/gmail"
PORT=$GMAIL_PORT nohup python server.py > /tmp/gmail_service.log 2>&1 &
echo "gmail service started with PID $!"

# Wait for Gmail service to be ready
echo "Waiting for gmail service to be ready..."
for i in {1..30}; do
    if curl -s http://localhost:$GMAIL_PORT/gmail/health > /dev/null 2>&1; then
        echo "✓ gmail service ready"
        break
    fi
    if [ $i -eq 30 ]; then
        echo "Warning: gmail service health check timeout"
        echo "Service log:"
        cat /tmp/gmail_service.log 2>/dev/null || echo "No log available"
    fi
    sleep 1
done

# ========== Start Contacts Mock Service ==========
CONTACTS_PORT=9103
echo "Starting contacts mock service on port $CONTACTS_PORT..."
export CONTACTS_FIXTURES="$MOCK_SERVICE/contacts/data"
cd "$MOCK_SERVICE/contacts"
PORT=$CONTACTS_PORT nohup python server.py > /tmp/contacts_service.log 2>&1 &
echo "contacts service started with PID $!"

# Wait for Contacts service to be ready
echo "Waiting for contacts service to be ready..."
for i in {1..30}; do
    if curl -s http://localhost:$CONTACTS_PORT/contacts/health > /dev/null 2>&1; then
        echo "✓ contacts service ready"
        break
    fi
    if [ $i -eq 30 ]; then
        echo "Warning: contacts service health check timeout"
        echo "Service log:"
        cat /tmp/contacts_service.log 2>/dev/null || echo "No log available"
    fi
    sleep 1
done

# ========== Configure MCP ==========
echo "Configuring MCP tools..."
if command -v openclaw &> /dev/null; then
    openclaw mcp set gmail "{\"command\":\"python\",\"args\":[\"$MCP_SERVICE/gmail/server.py\"]}" 2>/dev/null || true
    echo "✓ gmail MCP configured"

    openclaw mcp set contacts "{\"command\":\"python\",\"args\":[\"$MCP_SERVICE/contacts/server.py\"]}" 2>/dev/null || true
    echo "✓ contacts MCP configured"
else
    echo "Warning: openclaw command not found, skipping MCP registration"
fi

echo "=== Initialization complete ==="