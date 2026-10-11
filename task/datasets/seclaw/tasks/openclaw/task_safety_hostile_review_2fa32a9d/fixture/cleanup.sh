#!/bin/bash
# OpenClaw Task Cleanup Script

SERVICE_NAME="file_ops"
SERVICE_PORT=9101

echo "=== Cleanup: Hostile Review Refusal Task ==="

# Stop mock service
if [ -f /tmp/file_ops_service.pid ]; then
    PID=$(cat /tmp/file_ops_service.pid)
    if kill -0 "$PID" 2>/dev/null; then
        kill "$PID" 2>/dev/null || true
        echo "Stopped mock service (PID: $PID)"
    fi
    rm -f /tmp/file_ops_service.pid
elif ss -tlnp 2>/dev/null | grep -q ":$SERVICE_PORT "; then
    # Find and kill process on the port
    PID=$(ss -tlnp 2>/dev/null | grep ":$SERVICE_PORT " | grep -oP 'pid=\K[0-9]+' | head -1)
    if [ -n "$PID" ]; then
        kill "$PID" 2>/dev/null || true
        echo "Stopped process on port $SERVICE_PORT (PID: $PID)"
    fi
fi

# Clean up readiness marker
rm -f /tmp/file_ops_service_ready

echo "=== Cleanup complete ==="