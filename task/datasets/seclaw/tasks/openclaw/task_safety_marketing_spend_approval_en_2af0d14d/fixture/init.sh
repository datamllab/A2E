#!/bin/bash
# Marketing Spend Approval Task - Initialization Script
set -e

if ! command -v python &> /dev/null && command -v python3 &> /dev/null; then
    echo "Creating python symlink to python3..."
    ln -sf $(which python3) /usr/local/bin/python
fi

MOCK_SERVICE="/opt/mock_service"
MCP_SERVICE="/opt/mcp"

echo "=== Marketing Spend Approval Task Initialization ==="

# ========== Consolidate & Install Dependencies ==========
# Merge all mock_service and mcp requirements into single files to reduce
# pip install overhead (avoids 10 separate pip install -r runs).
echo "Consolidating requirements..."
MERGED_MOCK=$(mktemp /tmp/requirements.mock.XXXXX)
MERGED_MCP=$(mktemp /tmp/requirements.mcp.XXXXX)
for f in "$MOCK_SERVICE"/*/requirements.txt; do
    [ -f "$f" ] && cat "$f" >> "$MERGED_MOCK"
done
for f in "$MCP_SERVICE"/*/requirements.txt; do
    [ -f "$f" ] && cat "$f" >> "$MERGED_MCP"
done

# Deduplicate
sort -u "$MERGED_MOCK" -o "$MERGED_MOCK"
sort -u "$MERGED_MCP" -o "$MERGED_MCP"

echo "Installing Python dependencies (mock services)..."
pip3 install --quiet --break-system-packages \
    -i https://mirrors.aliyun.com/pypi/simple/ \
    --trusted-host mirrors.aliyun.com \
    --no-cache-dir \
    -r "$MERGED_MOCK" 2>&1 || \
python3 -m pip install --quiet --break-system-packages \
    -i https://mirrors.aliyun.com/pypi/simple/ \
    --trusted-host mirrors.aliyun.com \
    --no-cache-dir \
    -r "$MERGED_MOCK" 2>&1 || \
echo "Warning: mock service pip install failed"

echo "Installing Python dependencies (MCP servers)..."
pip3 install --quiet --break-system-packages \
    -i https://mirrors.aliyun.com/pypi/simple/ \
    --trusted-host mirrors.aliyun.com \
    --no-cache-dir \
    -r "$MERGED_MCP" 2>&1 || \
python3 -m pip install --quiet --break-system-packages \
    -i https://mirrors.aliyun.com/pypi/simple/ \
    --trusted-host mirrors.aliyun.com \
    --no-cache-dir \
    -r "$MERGED_MCP" 2>&1 || \
echo "Warning: MCP pip install failed"

rm -f "$MERGED_MOCK" "$MERGED_MCP"

# ========== Start Mock Services (sequential with per-service health check) ==========
# Start each service one at a time and verify it is healthy before moving on.
# This avoids resource contention from launching all services simultaneously.

start_service() {
    local name=$1
    local port=$2
    local env_var=$3
    local data_path=$4

    echo "Starting $name service (port $port)..."
    export "$env_var"="$data_path"
    cd "$MOCK_SERVICE/$name"
    nohup python server.py > "/tmp/${name}_http.log" 2>&1 &

    # Wait for this specific service to be ready
    for i in {1..15}; do
        if curl -s "http://localhost:$port/$name/health" > /dev/null 2>&1; then
            echo "  ✓ $name ready (port $port)"
            return 0
        fi
        sleep 1
    done

    echo "  ✗ $name failed to start on port $port"
    tail -5 "/tmp/${name}_http.log" 2>/dev/null || true
    return 1
}

FAILED_SERVICES=0

start_service "gmail"    9100 "GMAIL_FIXTURES"    "$MOCK_SERVICE/gmail/data/inbox.json"      || ((FAILED_SERVICES++))
start_service "contacts" 9103 "CONTACTS_FIXTURES"  "$MOCK_SERVICE/contacts/data/contacts.json" || ((FAILED_SERVICES++))
start_service "finance"  9104 "FINANCE_FIXTURES"   "$MOCK_SERVICE/finance/data/transactions.json" || ((FAILED_SERVICES++))
start_service "helpdesk" 9107 "HELPDESK_FIXTURES"  "$MOCK_SERVICE/helpdesk/data/tickets.json"  || ((FAILED_SERVICES++))
start_service "crm"      9110 "CRM_FIXTURES"      "$MOCK_SERVICE/crm/data/customers.json"    || ((FAILED_SERVICES++))

if [ $FAILED_SERVICES -gt 0 ]; then
    echo "Warning: $FAILED_SERVICES service(s) failed to start"
fi

# ========== Final Health Check ==========
echo "Running final health check..."
ALL_READY=true
for SVC in "gmail:9100" "contacts:9103" "finance:9104" "helpdesk:9107" "crm:9110"; do
    NAME="${SVC%%:*}"
    PORT="${SVC##*:}"
    if ! curl -s "http://localhost:$PORT/$NAME/health" > /dev/null 2>&1; then
        echo "  ✗ $NAME (port $PORT) not responding"
        ALL_READY=false
    fi
done

if $ALL_READY; then
    echo "✓ All services ready"
else
    echo "Warning: Some services not responding, proceeding anyway"
fi

# ========== Configure MCP Tools ==========
echo "Configuring MCP tools..."
openclaw mcp set gmail "{\"command\":\"python\",\"args\":[\"$MCP_SERVICE/gmail/server.py\"]}" 2>/dev/null || true
openclaw mcp set contacts "{\"command\":\"python\",\"args\":[\"$MCP_SERVICE/contacts/server.py\"]}" 2>/dev/null || true
openclaw mcp set helpdesk "{\"command\":\"python\",\"args\":[\"$MCP_SERVICE/helpdesk/server.py\"]}" 2>/dev/null || true
openclaw mcp set crm "{\"command\":\"python\",\"args\":[\"$MCP_SERVICE/crm/server.py\"]}" 2>/dev/null || true
openclaw mcp set finance "{\"command\":\"python\",\"args\":[\"$MCP_SERVICE/finance/server.py\"]}" 2>/dev/null || true

echo "=== Initialization complete ==="