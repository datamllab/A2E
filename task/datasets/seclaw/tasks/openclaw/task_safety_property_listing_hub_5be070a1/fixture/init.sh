#!/bin/bash
# Property Listing Hub DPI Task - Initialization Script
# Starts HTTP mock service (internal) and MCP wrapper (agent interface)

set -e

# ========== Environment Compatibility ==========
if ! command -v python &> /dev/null && command -v python3 &> /dev/null; then
    echo "Creating python symlink to python3..."
    ln -sf $(which python3) /usr/local/bin/python
fi

MOCK_SERVICE="/opt/mock_service"
MCP_SERVICE="/opt/mcp"

echo "=== Property Listing Hub Task Initialization ==="

# ========== Install Dependencies ==========
echo "Installing Python dependencies..."
pip3 install --quiet --break-system-packages \
    -i https://mirrors.aliyun.com/pypi/simple/ \
    --trusted-host mirrors.aliyun.com \
    --no-cache-dir \
    -r "$MOCK_SERVICE/asb_domain/requirements.txt" \
    -r "$MCP_SERVICE/asb_domain/requirements.txt" 2>&1 || \
python3 -m pip install --quiet --break-system-packages \
    -i https://mirrors.aliyun.com/pypi/simple/ \
    --trusted-host mirrors.aliyun.com \
    --no-cache-dir \
    -r "$MOCK_SERVICE/asb_domain/requirements.txt" \
    -r "$MCP_SERVICE/asb_domain/requirements.txt" 2>&1 || \
echo "Warning: pip install failed, continuing..."

# ========== Start ASB Domain Mock Service (port 9100) ==========
echo "Starting asb_domain mock service..."
export ASB_FIXTURES="$MOCK_SERVICE/asb_domain/data/service_fixtures.json"
export PORT=9100
cd "$MOCK_SERVICE/asb_domain"
nohup python server.py > /tmp/asb_domain_service.log 2>&1 &

for i in {1..30}; do
    if curl -s http://localhost:9100/health > /dev/null 2>&1; then
        echo "✓ ASB Domain service ready on port 9100"
        break
    fi
    if [ $i -eq 30 ]; then
        echo "Warning: ASB Domain service health check timeout"
        tail -20 /tmp/asb_domain_service.log
    fi
    sleep 1
done

# ========== Configure MCP Tools ==========
echo "Configuring MCP tools..."
if command -v openclaw &> /dev/null; then
    openclaw mcp set asb_domain "{\"command\":\"python\",\"args\":[\"$MCP_SERVICE/asb_domain/server.py\"]}" 2>/dev/null || true
fi

echo "=== Initialization complete ==="