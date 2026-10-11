#!/bin/bash
# Vendor Refund Triage Task - Initialization Script
# Starts HTTP mock services (internal) and MCP wrappers (agent interface)

set -e

# ========== 环境兼容性处理 ==========
if ! command -v python &> /dev/null && command -v python3 &> /dev/null; then
    echo "Creating python symlink to python3..."
    ln -sf $(which python3) /usr/local/bin/python
fi

MOCK_SERVICE="/opt/mock_service"
MCP_SERVICE="/opt/mcp"

echo "=== Vendor Refund Triage Task Initialization ==="

# ========== 安装依赖 ==========
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
echo "Warning: pip install failed"

# ========== 启动 Gmail Mock 服务 ==========
echo "Starting gmail mock service..."
export GMAIL_FIXTURES="$MOCK_SERVICE/gmail/data/inbox.json"
cd "$MOCK_SERVICE/gmail"
nohup python server.py > /tmp/gmail_http.log 2>&1 &
echo "Gmail service PID: $!"

# ========== 启动 Contacts Mock 服务 ==========
echo "Starting contacts mock service..."
export CONTACTS_FIXTURES="$MOCK_SERVICE/contacts/data/contacts.json"
cd "$MOCK_SERVICE/contacts"
nohup python server.py > /tmp/contacts_http.log 2>&1 &
echo "Contacts service PID: $!"

# ========== 启动 Helpdesk Mock 服务 ==========
echo "Starting helpdesk mock service..."
export HELPDESK_FIXTURES="$MOCK_SERVICE/helpdesk/data/tickets.json"
cd "$MOCK_SERVICE/helpdesk"
nohup python server.py > /tmp/helpdesk_http.log 2>&1 &
echo "Helpdesk service PID: $!"

# ========== 启动 CRM Mock 服务 ==========
echo "Starting crm mock service..."
export CRM_FIXTURES="$MOCK_SERVICE/crm/data/customers.json"
cd "$MOCK_SERVICE/crm"
nohup python server.py > /tmp/crm_http.log 2>&1 &
echo "CRM service PID: $!"

# ========== 启动 Finance Mock 服务 ==========
echo "Starting finance mock service..."
export FINANCE_FIXTURES="$MOCK_SERVICE/finance/data/transactions.json"
cd "$MOCK_SERVICE/finance"
nohup python server.py > /tmp/finance_http.log 2>&1 &
echo "Finance service PID: $!"

# ========== 等待所有服务就绪 ==========
echo "Waiting for services to be ready..."
ALL_READY=false
for i in {1..30}; do
    READY=true
    for SVC_URL in \
        "http://localhost:9100/gmail/health" \
        "http://localhost:9103/contacts/health" \
        "http://localhost:9107/helpdesk/health" \
        "http://localhost:9110/crm/health" \
        "http://localhost:9104/finance/health"; do
        if ! curl -s "$SVC_URL" > /dev/null 2>&1; then
            READY=false
            break
        fi
    done
    if [ "$READY" = true ]; then
        ALL_READY=true
        echo "✓ All services ready"
        break
    fi
    sleep 1
done

if [ "$ALL_READY" = false ]; then
    echo "Warning: Some services may not be ready"
    for LOG in /tmp/gmail_http.log /tmp/contacts_http.log /tmp/helpdesk_http.log /tmp/crm_http.log /tmp/finance_http.log; do
        if [ -f "$LOG" ]; then
            echo "--- $(basename $LOG) ---"
            tail -3 "$LOG" 2>/dev/null || true
        fi
    done
fi

# ========== 配置 MCP（注册工具到 OpenClaw） ==========
echo "Configuring MCP tools..."
openclaw mcp set gmail "{\"command\":\"python\",\"args\":[\"$MCP_SERVICE/gmail/server.py\"]}" 2>/dev/null || true
openclaw mcp set contacts "{\"command\":\"python\",\"args\":[\"$MCP_SERVICE/contacts/server.py\"]}" 2>/dev/null || true
openclaw mcp set helpdesk "{\"command\":\"python\",\"args\":[\"$MCP_SERVICE/helpdesk/server.py\"]}" 2>/dev/null || true
openclaw mcp set crm "{\"command\":\"python\",\"args\":[\"$MCP_SERVICE/crm/server.py\"]}" 2>/dev/null || true
openclaw mcp set finance "{\"command\":\"python\",\"args\":[\"$MCP_SERVICE/finance/server.py\"]}" 2>/dev/null || true

echo "=== Initialization complete ==="