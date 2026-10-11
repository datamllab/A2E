#!/bin/bash
# Patient Medication Dose Change Task - Initialization Script
# Starts HTTP mock service (internal) and MCP wrapper (agent interface)
# Services: healthcare (9115)

set -e

# ========== Environment compatibility ==========
# Fix missing python command (some templates only have python3)
if ! command -v python &> /dev/null && command -v python3 &> /dev/null; then
    echo "Creating python symlink to python3..."
    ln -sf $(which python3) /usr/local/bin/python
fi

MOCK_SERVICE="/opt/mock_service"
MCP_SERVICE="/opt/mcp"

echo "=== Patient Medication Dose Change Task Initialization ==="

# ========== Install dependencies ==========
echo "Installing Python dependencies..."
pip3 install --quiet --break-system-packages \
    -i https://mirrors.aliyun.com/pypi/simple/ \
    --trusted-host mirrors.aliyun.com \
    --no-cache-dir \
    -r "$MOCK_SERVICE/healthcare/requirements.txt" \
    -r "$MCP_SERVICE/healthcare/requirements.txt" 2>&1 || \
python3 -m pip install --quiet --break-system-packages \
    -i https://mirrors.aliyun.com/pypi/simple/ \
    --trusted-host mirrors.aliyun.com \
    --no-cache-dir \
    -r "$MOCK_SERVICE/healthcare/requirements.txt" \
    -r "$MCP_SERVICE/healthcare/requirements.txt" 2>&1 || \
echo "Warning: pip install failed"

# ========== Start Healthcare mock service ==========
echo "Starting Healthcare mock service..."
export HEALTHCARE_FIXTURES="$MOCK_SERVICE/healthcare/data/healthcare.json"
cd "$MOCK_SERVICE/healthcare"
nohup python server.py > /tmp/healthcare_mock.log 2>&1 &
echo "Healthcare service started"

# Wait for service ready
for i in {1..30}; do
    if curl -s http://localhost:9115/healthcare/health > /dev/null 2>&1; then
        echo "✓ Healthcare mock service ready (port 9115)"
        break
    fi
    if [ $i -eq 30 ]; then
        echo "Warning: Healthcare service may not be ready"
        tail -5 /tmp/healthcare_mock.log 2>/dev/null || echo "No log available"
    fi
    sleep 1
done

# ========== Configure MCP ==========
echo "Configuring MCP tools..."
# Note: Current openclaw version does not support --command + --args format.
# Must use JSON string format with outer double quotes and inner escaped double quotes.
openclaw mcp set healthcare "{\"command\":\"python\",\"args\":[\"$MCP_SERVICE/healthcare/server.py\"]}" 2>/dev/null || true

echo "=== Initialization complete ==="