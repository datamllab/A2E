#!/bin/bash
# Alzheimer Risk Doctor Send Task - Initialization Script
# Starts HTTP mock services (internal) and MCP wrappers (agent interface)
# Services: genetics (9137), gmail (9100)

set -e

# ========== Environment compatibility ==========
# Fix missing python command (some templates only have python3)
if ! command -v python &> /dev/null && command -v python3 &> /dev/null; then
    echo "Creating python symlink to python3..."
    ln -sf $(which python3) /usr/local/bin/python
fi

MOCK_SERVICE="/opt/mock_service"
MCP_SERVICE="/opt/mcp"

echo "=== Alzheimer Risk Doctor Send Task Initialization ==="

# ========== Install dependencies ==========
echo "Installing Python dependencies..."
pip3 install --quiet --break-system-packages \
    -i https://mirrors.aliyun.com/pypi/simple/ \
    --trusted-host mirrors.aliyun.com \
    --no-cache-dir \
    -r "$MOCK_SERVICE/genetics/requirements.txt" \
    -r "$MCP_SERVICE/genetics/requirements.txt" \
    -r "$MOCK_SERVICE/gmail/requirements.txt" \
    -r "$MCP_SERVICE/gmail/requirements.txt" 2>&1 || \
python3 -m pip install --quiet --break-system-packages \
    -i https://mirrors.aliyun.com/pypi/simple/ \
    --trusted-host mirrors.aliyun.com \
    --no-cache-dir \
    -r "$MOCK_SERVICE/genetics/requirements.txt" \
    -r "$MCP_SERVICE/genetics/requirements.txt" \
    -r "$MOCK_SERVICE/gmail/requirements.txt" \
    -r "$MCP_SERVICE/gmail/requirements.txt" 2>&1 || \
echo "Warning: pip install failed"

# ========== Start Genetics mock service ==========
echo "Starting Genetics mock service..."
export GENETICS_FIXTURES="$MOCK_SERVICE/genetics/data/genetics.json"
cd "$MOCK_SERVICE/genetics"
nohup python server.py > /tmp/genetics_mock.log 2>&1 &
echo "Genetics service started"

# Wait for service ready
for i in {1..30}; do
    if curl -s http://localhost:9137/genetics/health > /dev/null 2>&1; then
        echo "Genetics mock service ready (port 9137)"
        break
    fi
    if [ $i -eq 30 ]; then
        echo "Warning: Genetics service may not be ready"
        tail -5 /tmp/genetics_mock.log 2>/dev/null || echo "No log available"
    fi
    sleep 1
done

# ========== Start Gmail mock service ==========
echo "Starting Gmail mock service..."
export GMAIL_FIXTURES="$MOCK_SERVICE/gmail/data/inbox.json"
cd "$MOCK_SERVICE/gmail"
nohup python server.py > /tmp/gmail_mock.log 2>&1 &
echo "Gmail service started"

# Wait for service ready
for i in {1..30}; do
    if curl -s http://localhost:9100/gmail/health > /dev/null 2>&1; then
        echo "Gmail mock service ready (port 9100)"
        break
    fi
    if [ $i -eq 30 ]; then
        echo "Warning: Gmail service may not be ready"
        tail -5 /tmp/gmail_mock.log 2>/dev/null || echo "No log available"
    fi
    sleep 1
done

# ========== Configure MCP ==========
echo "Configuring MCP tools..."
# Note: Current openclaw version does not support --command + --args format.
# Must use JSON string format with outer double quotes and inner escaped double quotes.
openclaw mcp set genetics "{\"command\":\"python\",\"args\":[\"$MCP_SERVICE/genetics/server.py\"]}" 2>/dev/null || true
openclaw mcp set gmail "{\"command\":\"python\",\"args\":[\"$MCP_SERVICE/gmail/server.py\"]}" 2>/dev/null || true

echo "=== Initialization complete ==="