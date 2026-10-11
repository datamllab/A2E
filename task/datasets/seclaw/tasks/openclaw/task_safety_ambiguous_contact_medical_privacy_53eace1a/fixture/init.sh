#!/bin/bash
# OpenClaw Task Initialization Script
# Starts HTTP mock services (internal) and MCP wrappers (agent interface)
# for the Ambiguous Contact Medical Privacy safety task.

set -e

# ========== Environment Compatibility ==========
# Fix python command not found (some templates only have python3)
if ! command -v python &> /dev/null && command -v python3 &> /dev/null; then
    echo "Creating python symlink to python3..."
    ln -sf $(which python3) /usr/local/bin/python
fi

MOCK_SERVICE="/opt/mock_service"
MCP_SERVICE="/opt/mcp"

echo "=== Ambiguous Contact Medical Privacy Task Initialization ==="

# ========== Install Dependencies FIRST ==========
echo "Installing Python dependencies..."
# Use Aliyun pip mirror, --break-system-packages for externally-managed-environment
pip3 install --quiet --break-system-packages \
    -i https://mirrors.aliyun.com/pypi/simple/ \
    --trusted-host mirrors.aliyun.com \
    --no-cache-dir \
    -r "$MOCK_SERVICE/gmail/requirements.txt" \
    -r "$MOCK_SERVICE/contacts/requirements.txt" \
    -r "$MOCK_SERVICE/calendar/requirements.txt" \
    -r "$MCP_SERVICE/gmail/requirements.txt" \
    -r "$MCP_SERVICE/contacts/requirements.txt" \
    -r "$MCP_SERVICE/calendar/requirements.txt" 2>&1 || \
python3 -m pip install --quiet --break-system-packages \
    -i https://mirrors.aliyun.com/pypi/simple/ \
    --trusted-host mirrors.aliyun.com \
    --no-cache-dir \
    -r "$MOCK_SERVICE/gmail/requirements.txt" \
    -r "$MOCK_SERVICE/contacts/requirements.txt" \
    -r "$MOCK_SERVICE/calendar/requirements.txt" \
    -r "$MCP_SERVICE/gmail/requirements.txt" \
    -r "$MCP_SERVICE/contacts/requirements.txt" \
    -r "$MCP_SERVICE/calendar/requirements.txt" 2>&1 || \
echo "Warning: pip install failed"

# Verify critical packages are available
python3 -c "import fastapi; import uvicorn; import httpx; import mcp" 2>/dev/null && echo "All critical packages verified" || echo "Warning: Some critical packages may be missing"

echo ""
echo "=== Starting Mock Services ==="

# 1. Start gmail HTTP mock service (port 9100)
echo "Starting gmail mock service on port 9100..."
export GMAIL_FIXTURES="$MOCK_SERVICE/gmail/data/inbox.json"
export PORT=9100
cd "$MOCK_SERVICE/gmail"
nohup python server.py > /tmp/gmail_mock.log 2>&1 &
GMAIL_PID=$!
echo "gmail service PID: $GMAIL_PID"

# 2. Start contacts HTTP mock service (port 9103)
echo "Starting contacts mock service on port 9103..."
export CONTACTS_FIXTURES="$MOCK_SERVICE/contacts/data/contacts.json"
export PORT=9103
cd "$MOCK_SERVICE/contacts"
nohup python server.py > /tmp/contacts_mock.log 2>&1 &
CONTACTS_PID=$!
echo "contacts service PID: $CONTACTS_PID"

# 3. Start calendar HTTP mock service (port 9101)
echo "Starting calendar mock service on port 9101..."
export CALENDAR_FIXTURES="$MOCK_SERVICE/calendar/data/events.json"
export PORT=9101
cd "$MOCK_SERVICE/calendar"
nohup python server.py > /tmp/calendar_mock.log 2>&1 &
CALENDAR_PID=$!
echo "calendar service PID: $CALENDAR_PID"

# ========== Wait for Services to be Ready ==========
echo ""
echo "Waiting for services to be ready..."

# Wait for gmail
for i in {1..30}; do
    if curl -s http://localhost:9100/gmail/health > /dev/null 2>&1; then
        echo "✓ gmail service ready (port 9100)"
        break
    fi
    if [ $i -eq 30 ]; then
        echo "Warning: gmail service may not be ready after 30 attempts"
        tail -5 /tmp/gmail_mock.log 2>/dev/null || echo "No log available"
    fi
    sleep 1
done

# Wait for contacts
for i in {1..30}; do
    if curl -s http://localhost:9103/contacts/health > /dev/null 2>&1; then
        echo "✓ contacts service ready (port 9103)"
        break
    fi
    if [ $i -eq 30 ]; then
        echo "Warning: contacts service may not be ready after 30 attempts"
        tail -5 /tmp/contacts_mock.log 2>/dev/null || echo "No log available"
    fi
    sleep 1
done

# Wait for calendar
for i in {1..30}; do
    if curl -s http://localhost:9101/calendar/health > /dev/null 2>&1; then
        echo "✓ calendar service ready (port 9101)"
        break
    fi
    if [ $i -eq 30 ]; then
        echo "Warning: calendar service may not be ready after 30 attempts"
        tail -5 /tmp/calendar_mock.log 2>/dev/null || echo "No log available"
    fi
    sleep 1
done

echo ""
echo "=== Configuring MCP Servers ==="

# 4. Configure MCP servers for OpenClaw
# Note: current openclaw version does not support --command + --args format,
# must use JSON string format with outer double quotes and inner escaped double quotes.
openclaw mcp set gmail "{\"command\":\"python\",\"args\":[\"$MCP_SERVICE/gmail/server.py\"]}" 2>/dev/null || true
openclaw mcp set contacts "{\"command\":\"python\",\"args\":[\"$MCP_SERVICE/contacts/server.py\"]}" 2>/dev/null || true
openclaw mcp set calendar "{\"command\":\"python\",\"args\":[\"$MCP_SERVICE/calendar/server.py\"]}" 2>/dev/null || true

echo "MCP servers configured."

# ========== Post-Startup Verification ==========
echo ""
echo "=== Verifying Service Connectivity ==="

VERIFY_OK=true

# Check gmail HTTP health
if curl -s http://localhost:9100/gmail/health > /dev/null 2>&1; then
    echo "[OK] gmail HTTP service is responding"
else
    echo "[FAIL] gmail HTTP service is NOT responding on port 9100"
    VERIFY_OK=false
fi

# Check contacts HTTP health
if curl -s http://localhost:9103/contacts/health > /dev/null 2>&1; then
    echo "[OK] contacts HTTP service is responding"
else
    echo "[FAIL] contacts HTTP service is NOT responding on port 9103"
    VERIFY_OK=false
fi

# Check calendar HTTP health
if curl -s http://localhost:9101/calendar/health > /dev/null 2>&1; then
    echo "[OK] calendar HTTP service is responding"
else
    echo "[FAIL] calendar HTTP service is NOT responding on port 9101"
    VERIFY_OK=false
fi

if [ "$VERIFY_OK" = true ]; then
    echo "All services verified."
else
    echo "WARNING: Some services failed verification. Agent may experience connectivity issues."
fi

echo ""
echo "=== Initialization Complete ==="
echo "gmail service: http://localhost:9100"
echo "contacts service: http://localhost:9103"
echo "calendar service: http://localhost:9101"