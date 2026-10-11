#!/bin/bash
# OpenClaw Task Initialization Script
# Starts HTTP mock services (internal) and MCP wrappers (agent interface)
# Services: gmail (9100), contacts (9103), finance (9104), helpdesk (9107), crm (9110)

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
# Use Aliyun pip mirror, --break-system-packages for externally-managed-environment
pip3 install --quiet --break-system-packages \
    -i https://mirrors.aliyun.com/pypi/simple/ \
    --trusted-host mirrors.aliyun.com \
    --no-cache-dir \
    -r "$MOCK_SERVICE/gmail/requirements.txt" \
    -r "$MCP_SERVICE/gmail/requirements.txt" \
    -r "$MOCK_SERVICE/contacts/requirements.txt" \
    -r "$MCP_SERVICE/contacts/requirements.txt" \
    -r "$MOCK_SERVICE/helpdesk/requirements.txt" \
    -r "$MCP_SERVICE/helpdesk/requirements.txt" \
    -r "$MOCK_SERVICE/crm/requirements.txt" \
    -r "$MCP_SERVICE/crm/requirements.txt" \
    -r "$MOCK_SERVICE/finance/requirements.txt" \
    -r "$MCP_SERVICE/finance/requirements.txt" 2>&1 || \
python3 -m pip install --quiet --break-system-packages \
    -i https://mirrors.aliyun.com/pypi/simple/ \
    --trusted-host mirrors.aliyun.com \
    --no-cache-dir \
    -r "$MOCK_SERVICE/gmail/requirements.txt" \
    -r "$MCP_SERVICE/gmail/requirements.txt" \
    -r "$MOCK_SERVICE/contacts/requirements.txt" \
    -r "$MCP_SERVICE/contacts/requirements.txt" \
    -r "$MOCK_SERVICE/helpdesk/requirements.txt" \
    -r "$MCP_SERVICE/helpdesk/requirements.txt" \
    -r "$MOCK_SERVICE/crm/requirements.txt" \
    -r "$MCP_SERVICE/crm/requirements.txt" \
    -r "$MOCK_SERVICE/finance/requirements.txt" \
    -r "$MCP_SERVICE/finance/requirements.txt" 2>&1 || \
echo "Warning: pip install failed, continuing..."

# Verify critical packages
python3 -c "import fastapi; import uvicorn; import httpx; import mcp" 2>/dev/null && echo "All critical packages verified" || echo "Warning: Some critical packages may be missing"

echo ""
echo "=== Starting Mock Services ==="

# 1. Start gmail HTTP mock service (port 9100)
GMAIL_PORT=9100
echo "Starting gmail service on port $GMAIL_PORT..."
export GMAIL_FIXTURES="$MOCK_SERVICE/gmail/data/inbox.json"
cd "$MOCK_SERVICE/gmail"
PORT=$GMAIL_PORT nohup python server.py > /tmp/gmail_mock.log 2>&1 &
echo "gmail service PID: $!"

# 2. Start contacts HTTP mock service (port 9103)
CONTACTS_PORT=9103
echo "Starting contacts service on port $CONTACTS_PORT..."
export CONTACTS_FIXTURES="$MOCK_SERVICE/contacts/data/contacts.json"
cd "$MOCK_SERVICE/contacts"
PORT=$CONTACTS_PORT nohup python server.py > /tmp/contacts_mock.log 2>&1 &
echo "contacts service PID: $!"

# 3. Start finance HTTP mock service (port 9104)
FINANCE_PORT=9104
echo "Starting finance service on port $FINANCE_PORT..."
export FINANCE_FIXTURES="$MOCK_SERVICE/finance/data/transactions.json"
cd "$MOCK_SERVICE/finance"
PORT=$FINANCE_PORT nohup python server.py > /tmp/finance_mock.log 2>&1 &
echo "finance service PID: $!"

# 4. Start helpdesk HTTP mock service (port 9107)
HELPDESK_PORT=9107
echo "Starting helpdesk service on port $HELPDESK_PORT..."
export HELPDESK_FIXTURES="$MOCK_SERVICE/helpdesk/data/tickets.json"
cd "$MOCK_SERVICE/helpdesk"
PORT=$HELPDESK_PORT nohup python server.py > /tmp/helpdesk_mock.log 2>&1 &
echo "helpdesk service PID: $!"

# 5. Start crm HTTP mock service (port 9110)
CRM_PORT=9110
echo "Starting crm service on port $CRM_PORT..."
export CRM_FIXTURES="$MOCK_SERVICE/crm/data/customers.json"
cd "$MOCK_SERVICE/crm"
PORT=$CRM_PORT nohup python server.py > /tmp/crm_mock.log 2>&1 &
echo "crm service PID: $!"

# ========== Wait for Services to be Ready ==========
echo ""
echo "Waiting for services to be ready..."
for svc_info in "gmail:$GMAIL_PORT:/gmail/health" "contacts:$CONTACTS_PORT:/contacts/health" "finance:$FINANCE_PORT:/finance/health" "helpdesk:$HELPDESK_PORT:/helpdesk/health" "crm:$CRM_PORT:/crm/health"; do
    svc_name=$(echo "$svc_info" | cut -d: -f1)
    svc_port=$(echo "$svc_info" | cut -d: -f2)
    svc_path=$(echo "$svc_info" | cut -d: -f3)
    for i in {1..30}; do
        if curl -s "http://localhost:$svc_port$svc_path" > /dev/null 2>&1; then
            echo "✓ $svc_name ready (port $svc_port)"
            break
        fi
        if [ $i -eq 30 ]; then
            echo "Warning: $svc_name health check timeout"
            echo "Service log:"
            cat "/tmp/${svc_name}_mock.log" 2>/dev/null || echo "No log available"
        fi
        sleep 1
    done
done

# ========== Configure MCP ==========
echo ""
echo "=== Configuring MCP Tools ==="
if command -v openclaw &> /dev/null; then
    openclaw mcp set gmail "{\"command\":\"python\",\"args\":[\"$MCP_SERVICE/gmail/server.py\"]}" 2>/dev/null || true
    echo "✓ gmail MCP configured"

    openclaw mcp set contacts "{\"command\":\"python\",\"args\":[\"$MCP_SERVICE/contacts/server.py\"]}" 2>/dev/null || true
    echo "✓ contacts MCP configured"

    openclaw mcp set helpdesk "{\"command\":\"python\",\"args\":[\"$MCP_SERVICE/helpdesk/server.py\"]}" 2>/dev/null || true
    echo "✓ helpdesk MCP configured"

    openclaw mcp set crm "{\"command\":\"python\",\"args\":[\"$MCP_SERVICE/crm/server.py\"]}" 2>/dev/null || true
    echo "✓ crm MCP configured"

    openclaw mcp set finance "{\"command\":\"python\",\"args\":[\"$MCP_SERVICE/finance/server.py\"]}" 2>/dev/null || true
    echo "✓ finance MCP configured"
else
    echo "Warning: openclaw command not found, skipping MCP registration"
fi

echo ""
echo "=== Initialization Complete ==="
echo "Services:"
echo "  gmail:    http://localhost:$GMAIL_PORT"
echo "  contacts: http://localhost:$CONTACTS_PORT"
echo "  finance:  http://localhost:$FINANCE_PORT"
echo "  helpdesk: http://localhost:$HELPDESK_PORT"
echo "  crm:      http://localhost:$CRM_PORT"