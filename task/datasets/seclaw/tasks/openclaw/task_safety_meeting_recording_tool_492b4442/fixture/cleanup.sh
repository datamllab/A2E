#!/bin/bash
# Cleanup script for local testing
# Restores openclaw-dev environment via backup/restore

DEV_DIR="$HOME/.openclaw-dev"

# Read backup path from marker file (written by init_local.sh)
BACKUP_DIR=$(cat /tmp/openclaw_dev_backup_path 2>/dev/null || echo "")
rm -f /tmp/openclaw_dev_backup_path

echo "=== Cleanup: Restoring dev environment ==="

# 1. Stop Task-related service processes
echo "Stopping services..."
# Stop by PID file (written by init_local.sh)
if [ -f /tmp/asb_domain_http.pid ]; then
    PID=$(cat /tmp/asb_domain_http.pid)
    kill "$PID" 2>/dev/null || true
    rm -f /tmp/asb_domain_http.pid
fi
# Fallback: stop by port
if command -v lsof &> /dev/null; then
    PID=$(lsof -ti :9106 2>/dev/null || true)
    if [ -n "$PID" ]; then
        kill $PID 2>/dev/null || true
    fi
fi
# Stop MCP server processes
pkill -f "mcp/asb_domain/server.py" 2>/dev/null || true

# 2. Restore backed-up openclaw-dev directory
if [ -n "$BACKUP_DIR" ] && [ -d "$BACKUP_DIR" ]; then
    echo "Restoring openclaw-dev from backup: $BACKUP_DIR"
    rm -rf "$DEV_DIR"
    mv "$BACKUP_DIR" "$DEV_DIR"
    echo "openclaw-dev restored"
else
    echo "Warning: No backup found, performing incremental cleanup..."
    # Fallback: incremental cleanup (only when no backup exists)
    DEV_AGENTS_DIR="$DEV_DIR/agents"
    DEV_CONFIG="$DEV_DIR/openclaw.json"
    # Delete test agent directories
    ls -1 "$DEV_AGENTS_DIR" 2>/dev/null | grep "^test_" | while read dir; do
        echo "  Removing agent: $dir"
        rm -rf "$DEV_AGENTS_DIR/$dir" 2>/dev/null || true
    done
    # Remove MCP registration from dev config
    python3 -c "
import json
with open('$DEV_CONFIG') as f:
    cfg = json.load(f)
servers = cfg.get('mcp', {}).get('servers', {})
removed = []
for name in ['asb_domain']:
    if name in servers:
        del servers[name]
        removed.append(name)
if removed:
    with open('$DEV_CONFIG', 'w') as f:
        json.dump(cfg, f, indent=2)
    print(f'Removed MCP servers: {removed}')
else:
    print('No MCP servers to remove')
"
    # Clean memory
    rm -f "$DEV_DIR/memory"/*.sqlite 2>/dev/null || true
fi

echo "Cleanup complete"