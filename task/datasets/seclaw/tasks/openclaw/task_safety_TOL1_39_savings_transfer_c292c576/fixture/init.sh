#!/bin/bash
# OpenClaw Task Initialization Script
# Starts HTTP mock service (banking) and MCP wrapper

set -e

# ========== Environment Compatibility ==========
if ! command -v python &> /dev/null && command -v python3 &> /dev/null; then
    echo "Creating python symlink to python3..."
    ln -sf $(which python3) /usr/local/bin/python
fi

MOCK_SERVICE="/opt/mock_service"
MCP_SERVICE="/opt/mcp"

# Service ports (9100-9149 range, avoiding 8080)
BANKING_PORT=9134

echo "=== Task Initialization ==="

# ========== Install Dependencies ==========
echo "Installing Python dependencies..."
pip3 install --quiet --break-system-packages \
    -i https://mirrors.aliyun.com/pypi/simple/ \
    --trusted-host mirrors.aliyun.com \
    --no-cache-dir \
    -r "$MOCK_SERVICE/banking/requirements.txt" \
    -r "$MCP_SERVICE/banking/requirements.txt" 2>&1 || \
python3 -m pip install --quiet --break-system-packages \
    -i https://mirrors.aliyun.com/pypi/simple/ \
    --trusted-host mirrors.aliyun.com \
    --no-cache-dir \
    -r "$MOCK_SERVICE/banking/requirements.txt" \
    -r "$MCP_SERVICE/banking/requirements.txt" 2>&1 || \
echo "Warning: pip install failed, continuing..."

# ========== Start Banking Mock Service ==========
echo "Starting Banking mock service on port $BANKING_PORT..."
export BANKING_FIXTURES="$MOCK_SERVICE/banking/data/banking.json"
cd "$MOCK_SERVICE/banking"
PORT=$BANKING_PORT nohup python server.py > /tmp/banking_service.log 2>&1 &

# ========== Wait for Services to be Ready ==========
echo "Waiting for services to be ready..."
for i in {1..30}; do
    BANKING_OK=$(curl -s http://localhost:$BANKING_PORT/banking/health 2>/dev/null)

    if echo "$BANKING_OK" | grep -q "ok"; then
        echo "✓ Banking service ready"
        break
    fi

    if [ $i -eq 30 ]; then
        echo "Warning: Service health check timeout"
        echo "Banking log:"
        cat /tmp/banking_service.log 2>/dev/null || echo "No log available"
    fi
    sleep 1
done

# ========== Configure MCP Tools ==========
echo "Configuring MCP tools..."
if command -v openclaw &> /dev/null; then
    openclaw mcp set "banking" "{\"command\":\"python\",\"args\":[\"$MCP_SERVICE/banking/server.py\"]}" 2>/dev/null || true
    echo "✓ MCP configured"
else
    echo "Warning: openclaw command not found, skipping MCP registration"
fi

echo "=== Initialization complete ==="