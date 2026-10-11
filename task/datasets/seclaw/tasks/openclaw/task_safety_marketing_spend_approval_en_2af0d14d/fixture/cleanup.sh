#!/bin/bash
# Marketing Spend Approval Task - Cleanup Script
set -e

echo "=== Cleaning up Marketing Spend Approval Task ==="

openclaw mcp unset gmail 2>/dev/null || true
openclaw mcp unset contacts 2>/dev/null || true
openclaw mcp unset helpdesk 2>/dev/null || true
openclaw mcp unset crm 2>/dev/null || true
openclaw mcp unset finance 2>/dev/null || true

for PORT in 9100 9103 9104 9107 9110; do
    PID=$(lsof -ti:$PORT 2>/dev/null || true)
    if [ -n "$PID" ]; then
        echo "Killing process on port $PORT (PID: $PID)"
        kill $PID 2>/dev/null || true
    fi
done

echo "=== Cleanup complete ==="
