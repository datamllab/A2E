#!/bin/bash
# OpenClaw Task Initialization Script
# Starts HTTP mock services (internal) and MCP wrappers (agent interface)
# for the Incident Response Chain Defense task.

# ========== Environment Compatibility ==========
# Fix python command not found (some templates only have python3)
if ! command -v python &> /dev/null && command -v python3 &> /dev/null; then
    echo "Creating python symlink to python3..."
    ln -sf $(which python3) /usr/local/bin/python
fi

MOCK_SERVICE="/opt/mock_service"
MCP_SERVICE="/opt/mcp"

echo "=== Incident Response Chain Task Initialization ==="

# ========== Install Dependencies FIRST ==========
# CRITICAL: Dependencies must be installed before starting services,
# otherwise FastAPI/uvicorn will not be available and services will crash.
echo "Installing Python dependencies..."

# Mock service dependencies (Gmail)
pip3 install --quiet --break-system-packages \
    -i https://mirrors.aliyun.com/pypi/simple/ \
    --trusted-host mirrors.aliyun.com \
    --no-cache-dir \
    -r "$MOCK_SERVICE/gmail/requirements.txt" 2>&1 || \
python3 -m pip install --quiet --break-system-packages \
    -i https://mirrors.aliyun.com/pypi/simple/ \
    --trusted-host mirrors.aliyun.com \
    --no-cache-dir \
    -r "$MOCK_SERVICE/gmail/requirements.txt" 2>&1 || \
echo "Warning: Gmail mock service pip install failed"

# Mock service dependencies (Network)
pip3 install --quiet --break-system-packages \
    -i https://mirrors.aliyun.com/pypi/simple/ \
    --trusted-host mirrors.aliyun.com \
    --no-cache-dir \
    -r "$MOCK_SERVICE/network/requirements.txt" 2>&1 || \
python3 -m pip install --quiet --break-system-packages \
    -i https://mirrors.aliyun.com/pypi/simple/ \
    --trusted-host mirrors.aliyun.com \
    --no-cache-dir \
    -r "$MOCK_SERVICE/network/requirements.txt" 2>&1 || \
echo "Warning: Network mock service pip install failed"

# MCP server dependencies
pip3 install --quiet --break-system-packages \
    -i https://mirrors.aliyun.com/pypi/simple/ \
    --trusted-host mirrors.aliyun.com \
    --no-cache-dir \
    -r "$MCP_SERVICE/gmail/requirements.txt" \
    -r "$MCP_SERVICE/network/requirements.txt" 2>&1 || \
python3 -m pip install --quiet --break-system-packages \
    -i https://mirrors.aliyun.com/pypi/simple/ \
    --trusted-host mirrors.aliyun.com \
    --no-cache-dir \
    -r "$MCP_SERVICE/gmail/requirements.txt" \
    -r "$MCP_SERVICE/network/requirements.txt" 2>&1 || \
echo "Warning: MCP server pip install failed"

# Verify critical packages are available
python3 -c "import fastapi; import uvicorn; import httpx; import mcp" 2>/dev/null && echo "All critical packages verified" || echo "Warning: Some critical packages may be missing"

echo ""
echo "=== Starting Mock Services ==="

# 1. Start Gmail HTTP mock service (port 9100)
echo "Starting Gmail mock service on port 9100..."
export GMAIL_FIXTURES="$MOCK_SERVICE/gmail/data/gmail.json"
cd "$MOCK_SERVICE/gmail"
nohup python server.py > /tmp/gmail_mock.log 2>&1 &
GMAIL_PID=$!
echo "Gmail service PID: $GMAIL_PID"

# Wait for Gmail service to be ready
echo "Waiting for Gmail service..."
for i in {1..30}; do
    if curl -s http://localhost:9100/gmail/health > /dev/null 2>&1; then
        echo "Gmail service ready"
        break
    fi
    if [ $i -eq 30 ]; then
        echo "Warning: Gmail service may not be ready after 30 attempts"
        tail -5 /tmp/gmail_mock.log 2>/dev/null || echo "No log available"
    fi
    sleep 1
done

# 2. Start Network (PASB) HTTP mock service (port 9131)
echo "Starting Network mock service on port 9131..."
export PASB_FIXTURES="$MOCK_SERVICE/network/data"
export PORT=9131
cd "$MOCK_SERVICE/network"
nohup python server.py > /tmp/network_mock.log 2>&1 &
NETWORK_PID=$!
echo "Network service PID: $NETWORK_PID"

# Wait for Network service to be ready
echo "Waiting for Network service..."
for i in {1..30}; do
    if curl -s http://localhost:9131/pasb/health > /dev/null 2>&1; then
        echo "Network service ready"
        break
    fi
    if [ $i -eq 30 ]; then
        echo "Warning: Network service may not be ready after 30 attempts"
        tail -5 /tmp/network_mock.log 2>/dev/null || echo "No log available"
    fi
    sleep 1
done

echo ""
echo "=== Configuring MCP Servers ==="

# 3. Configure MCP servers for OpenClaw
openclaw mcp set gmail "{\"command\":\"python\",\"args\":[\"$MCP_SERVICE/gmail/server.py\"]}" 2>&1
openclaw mcp set network "{\"command\":\"python\",\"args\":[\"$MCP_SERVICE/network/server.py\"]}" 2>&1

echo "MCP servers configured."

# ========== Post-Startup Verification ==========
echo ""
echo "=== Verifying Service Connectivity ==="

VERIFY_OK=true

# Check Gmail HTTP health
if curl -s http://localhost:9100/gmail/health > /dev/null 2>&1; then
    echo "[OK] Gmail HTTP service is responding"
else
    echo "[FAIL] Gmail HTTP service is NOT responding on port 9100"
    VERIFY_OK=false
fi

# Check Network HTTP health
if curl -s http://localhost:9131/pasb/health > /dev/null 2>&1; then
    echo "[OK] Network HTTP service is responding"
else
    echo "[FAIL] Network HTTP service is NOT responding on port 9131"
    VERIFY_OK=false
fi

if [ "$VERIFY_OK" = true ]; then
    echo "All services verified."
else
    echo "WARNING: Some services failed verification. Agent may experience connectivity issues."
fi

echo ""
echo "=== Initialization Complete ==="
echo "Gmail service: http://localhost:9100"
echo "Network service: http://localhost:9131"