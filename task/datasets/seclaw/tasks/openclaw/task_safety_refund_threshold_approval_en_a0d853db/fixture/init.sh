#!/bin/bash
# OpenClaw Task Initialization Script
# Starts HTTP mock services (internal) and MCP wrappers (agent interface)
# Services: gmail (9100), contacts (9103), helpdesk (9107), crm (9110), finance (9104)

set -e

# ========== Environment Compatibility ==========
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
    -r "$MOCK_SERVICE/contacts/requirements.txt" \
    -r "$MOCK_SERVICE/helpdesk/requirements.txt" \
    -r "$MOCK_SERVICE/crm/requirements.txt" \
    -r "$MOCK_SERVICE/finance/requirements.txt" \
    -r "$MCP_SERVICE/gmail/requirements.txt" \
    -r "$MCP_SERVICE/contacts/requirements.txt" \
    -r "$MCP_SERVICE/helpdesk/requirements.txt" \
    -r "$MCP_SERVICE/crm/requirements.txt" \
    -r "$MCP_SERVICE/finance/requirements.txt" 2>&1 || \
python3 -m pip install --quiet --break-system-packages \
    -i https://mirrors.aliyun.com/pypi/simple/ \
    --trusted-host mirrors.aliyun.com \
    --no-cache-dir \
    -r "$MOCK_SERVICE/gmail/requirements.txt" \
    -r "$MOCK_SERVICE/contacts/requirements.txt" \
    -r "$MOCK_SERVICE/helpdesk/requirements.txt" \
    -r "$MOCK_SERVICE/crm/requirements.txt" \
    -r "$MOCK_SERVICE/finance/requirements.txt" \
    -r "$MCP_SERVICE/gmail/requirements.txt" \
    -r "$MCP_SERVICE/contacts/requirements.txt" \
    -r "$MCP_SERVICE/helpdesk/requirements.txt" \
    -r "$MCP_SERVICE/crm/requirements.txt" \
    -r "$MCP_SERVICE/finance/requirements.txt" 2>&1 || \
echo "Warning: pip install failed, attempting to continue"

# Verify critical imports
python3 -c "import mcp; import httpx" 2>/dev/null || echo "Warning: mcp or httpx import failed"

# ========== Start Mock Services ==========

# --- Gmail (port 9100) ---
echo "Starting gmail mock service on port 9100..."
export GMAIL_FIXTURES="$MOCK_SERVICE/gmail/data/inbox.json"
export PORT=9100
cd "$MOCK_SERVICE/gmail"
nohup python server.py > /tmp/gmail_service.log 2>&1 &
echo $! > /tmp/gmail_service.pid

# --- Contacts (port 9103) ---
echo "Starting contacts mock service on port 9103..."
export CONTACTS_FIXTURES="$MOCK_SERVICE/contacts/data/contacts.json"
export PORT=9103
cd "$MOCK_SERVICE/contacts"
nohup python server.py > /tmp/contacts_service.log 2>&1 &
echo $! > /tmp/contacts_service.pid

# --- Helpdesk (port 9107) ---
echo "Starting helpdesk mock service on port 9107..."
export HELPDESK_FIXTURES="$MOCK_SERVICE/helpdesk/data/tickets.json"
export PORT=9107
cd "$MOCK_SERVICE/helpdesk"
nohup python server.py > /tmp/helpdesk_service.log 2>&1 &
echo $! > /tmp/helpdesk_service.pid

# --- CRM (port 9110) ---
echo "Starting crm mock service on port 9110..."
export CRM_FIXTURES="$MOCK_SERVICE/crm/data/customers.json"
export PORT=9110
cd "$MOCK_SERVICE/crm"
nohup python server.py > /tmp/crm_service.log 2>&1 &
echo $! > /tmp/crm_service.pid

# --- Finance (port 9104) ---
echo "Starting finance mock service on port 9104..."
export FINANCE_FIXTURES="$MOCK_SERVICE/finance/data/transactions.json"
export PORT=9104
cd "$MOCK_SERVICE/finance"
nohup python server.py > /tmp/finance_service.log 2>&1 &
echo $! > /tmp/finance_service.pid

# ========== Wait for Services ==========
echo "Waiting for services to be ready..."
for i in {1..30}; do
    all_ready=true
    for svc_url in "http://localhost:9100/gmail/health" "http://localhost:9103/contacts/health" "http://localhost:9107/helpdesk/health" "http://localhost:9110/crm/health" "http://localhost:9104/finance/health"; do
        if ! curl -s "$svc_url" > /dev/null 2>&1; then
            all_ready=false
            break
        fi
    done
    if $all_ready; then
        echo "✓ All services ready"
        break
    fi
    sleep 1
done

if ! $all_ready; then
    echo "Warning: Some services may not be ready yet"
fi

# ========== Configure MCP ==========
echo "Configuring MCP tools..."
openclaw mcp set gmail "{\"command\":\"python\",\"args\":[\"$MCP_SERVICE/gmail/server.py\"]}" 2>/dev/null || true
openclaw mcp set contacts "{\"command\":\"python\",\"args\":[\"$MCP_SERVICE/contacts/server.py\"]}" 2>/dev/null || true
openclaw mcp set helpdesk "{\"command\":\"python\",\"args\":[\"$MCP_SERVICE/helpdesk/server.py\"]}" 2>/dev/null || true
openclaw mcp set crm "{\"command\":\"python\",\"args\":[\"$MCP_SERVICE/crm/server.py\"]}" 2>/dev/null || true
openclaw mcp set finance "{\"command\":\"python\",\"args\":[\"$MCP_SERVICE/finance/server.py\"]}" 2>/dev/null || true

echo "=== Initialization complete ==="