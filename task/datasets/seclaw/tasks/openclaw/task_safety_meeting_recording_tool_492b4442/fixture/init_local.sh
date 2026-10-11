#!/bin/bash
set -e

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
MOCK_SERVICE="$SCRIPT_DIR/mock_service"
MCP_SERVICE="$SCRIPT_DIR/mcp"
DEV_CONFIG="$HOME/.openclaw-dev/openclaw.json"
DEV_DIR="$HOME/.openclaw-dev"
BACKUP_DIR="$HOME/.openclaw-dev.bak.$$"

# Prefer project virtual environment
PROJECT_ROOT="$(cd "$(dirname "$0")/../../.." && pwd)"
if [ -f "$PROJECT_ROOT/.venv/bin/python" ]; then
    PYTHON="$PROJECT_ROOT/.venv/bin/python"
elif command -v python3.12 &> /dev/null; then
    PYTHON="python3.12"
elif command -v python3 &> /dev/null; then
    PYTHON="python3"
else
    echo "Error: Python 3.12+ required"
    exit 1
fi

echo "=== Task Initialization (local) ==="

# Backup openclaw-dev directory (cleanup.sh will restore this backup)
echo "Backing up openclaw-dev directory..."
cp -a "$DEV_DIR" "$BACKUP_DIR"

# Save backup path for cleanup.sh (cross-shell transfer)
echo "$BACKUP_DIR" > /tmp/openclaw_dev_backup_path

# Install dependencies
echo "Installing Python dependencies..."
$PYTHON -m pip install --quiet fastapi uvicorn pydantic httpx 2>/dev/null || true
$PYTHON -m pip install --quiet mcp 2>/dev/null || true

# Start HTTP mock service
echo "Starting mock service..."
export ASB_FIXTURES="$MOCK_SERVICE/asb_domain/data/service_data.json"
cd "$MOCK_SERVICE/asb_domain"
nohup $PYTHON server.py > /tmp/asb_domain_http.log 2>&1 &
HTTP_PID=$!
echo "$HTTP_PID" > /tmp/asb_domain_http.pid
echo "HTTP service PID: $HTTP_PID"

# Wait for service to be ready
echo "Waiting for HTTP service..."
for i in {1..30}; do
    if curl -s http://localhost:9106/asb/health > /dev/null 2>&1; then
        echo "HTTP service ready"
        break
    fi
    if [ $i -eq 30 ]; then
        echo "Warning: HTTP service may not be ready"
        tail -5 /tmp/asb_domain_http.log 2>/dev/null || echo "No log available"
    fi
    sleep 1
done

# Register MCP in dev config
echo "Configuring MCP tools (dev)..."
python3 -c "
import json
with open('$DEV_CONFIG') as f:
    cfg = json.load(f)
cfg.setdefault('mcp', {}).setdefault('servers', {})['asb_domain'] = {
    'command': '$(which $PYTHON)',
    'args': ['$MCP_SERVICE/asb_domain/server.py']
}
with open('$DEV_CONFIG', 'w') as f:
    json.dump(cfg, f, indent=2)
print('MCP registered in dev config')
"

echo "=== Initialization complete ==="