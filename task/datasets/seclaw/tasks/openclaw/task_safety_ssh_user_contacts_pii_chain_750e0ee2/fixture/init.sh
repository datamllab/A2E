#!/bin/bash
# OpenClaw Task Initialization Script
# Starts HTTP mock services (internal) and MCP wrappers (agent interface)
# for the SSH User Contacts PII Chain safety task.

set -e

# ========== Environment Compatibility ==========
# Fix python command not found (some templates only have python3)
if ! command -v python &> /dev/null && command -v python3 &> /dev/null; then
    echo "Creating python symlink to python3..."
    ln -sf $(which python3) /usr/local/bin/python
fi

MOCK_SERVICE="/opt/mock_service"
MCP_SERVICE="/opt/mcp"

echo "=== SSH User Contacts PII Chain Task Initialization ==="

# ========== Install Dependencies FIRST ==========
echo "Installing Python dependencies..."
# Use Aliyun pip mirror, --break-system-packages for externally-managed-environment
pip3 install --quiet --break-system-packages \
    -i https://mirrors.aliyun.com/pypi/simple/ \
    --trusted-host mirrors.aliyun.com \
    --no-cache-dir \
    -r "$MOCK_SERVICE/file_ops/requirements.txt" \
    -r "$MOCK_SERVICE/contacts/requirements.txt" \
    -r "$MCP_SERVICE/file_ops/requirements.txt" \
    -r "$MCP_SERVICE/contacts/requirements.txt" 2>&1 || \
python3 -m pip install --quiet --break-system-packages \
    -i https://mirrors.aliyun.com/pypi/simple/ \
    --trusted-host mirrors.aliyun.com \
    --no-cache-dir \
    -r "$MOCK_SERVICE/file_ops/requirements.txt" \
    -r "$MOCK_SERVICE/contacts/requirements.txt" \
    -r "$MCP_SERVICE/file_ops/requirements.txt" \
    -r "$MCP_SERVICE/contacts/requirements.txt" 2>&1 || \
echo "Warning: pip install failed"

# Verify critical packages are available
python3 -c "import fastapi; import uvicorn; import httpx; import mcp" 2>/dev/null && echo "All critical packages verified" || echo "Warning: Some critical packages may be missing"

echo ""
echo "=== Starting Mock Services ==="

# 1. Start file_ops HTTP mock service (port 9110)
echo "Starting file_ops mock service on port 9110..."
export FIXTURES_PATH="$MOCK_SERVICE/file_ops/data"
export PORT=9110
cd "$MOCK_SERVICE/file_ops"
nohup python server.py > /tmp/file_ops_mock.log 2>&1 &
FILE_OPS_PID=$!
echo "file_ops service PID: $FILE_OPS_PID"

# 2. Start contacts HTTP mock service (port 9111)
echo "Starting contacts mock service on port 9111..."
export CONTACTS_FIXTURES="$MOCK_SERVICE/contacts/data/contacts.json"
export PORT=9111
cd "$MOCK_SERVICE/contacts"
nohup python server.py > /tmp/contacts_mock.log 2>&1 &
CONTACTS_PID=$!
echo "contacts service PID: $CONTACTS_PID"

# ========== Wait for Services to be Ready ==========
echo ""
echo "Waiting for services to be ready..."

for i in {1..30}; do
    if curl -s http://localhost:9110/file_ops/health > /dev/null 2>&1; then
        echo "✓ file_ops service ready (port 9110)"
        break
    fi
    if [ $i -eq 30 ]; then
        echo "Warning: file_ops service may not be ready after 30 attempts"
        tail -5 /tmp/file_ops_mock.log 2>/dev/null || echo "No log available"
    fi
    sleep 1
done

for i in {1..30}; do
    if curl -s http://localhost:9111/contacts/health > /dev/null 2>&1; then
        echo "✓ contacts service ready (port 9111)"
        break
    fi
    if [ $i -eq 30 ]; then
        echo "Warning: contacts service may not be ready after 30 attempts"
        tail -5 /tmp/contacts_mock.log 2>/dev/null || echo "No log available"
    fi
    sleep 1
done

echo ""
echo "=== Configuring MCP Servers ==="

# 3. Configure MCP servers for OpenClaw
# Note: current openclaw version does not support --command + --args format,
# must use JSON string format with outer double quotes and inner escaped double quotes.
openclaw mcp set file_ops "{\"command\":\"python\",\"args\":[\"$MCP_SERVICE/file_ops/server.py\"]}" 2>/dev/null || true
openclaw mcp set contacts "{\"command\":\"python\",\"args\":[\"$MCP_SERVICE/contacts/server.py\"]}" 2>/dev/null || true

echo "MCP servers configured."

# ========== Post-Startup Verification ==========
echo ""
echo "=== Verifying Service Connectivity ==="

VERIFY_OK=true

# Check file_ops HTTP health
if curl -s http://localhost:9110/file_ops/health > /dev/null 2>&1; then
    echo "[OK] file_ops HTTP service is responding"
else
    echo "[FAIL] file_ops HTTP service is NOT responding on port 9110"
    VERIFY_OK=false
fi

# Check contacts HTTP health
if curl -s http://localhost:9111/contacts/health > /dev/null 2>&1; then
    echo "[OK] contacts HTTP service is responding"
else
    echo "[FAIL] contacts HTTP service is NOT responding on port 9111"
    VERIFY_OK=false
fi

if [ "$VERIFY_OK" = true ]; then
    echo "All services verified."
else
    echo "WARNING: Some services failed verification. Agent may experience connectivity issues."
fi

echo ""
echo "=== Initialization Complete ==="
echo "file_ops service: http://localhost:9110"
echo "contacts service: http://localhost:9111"