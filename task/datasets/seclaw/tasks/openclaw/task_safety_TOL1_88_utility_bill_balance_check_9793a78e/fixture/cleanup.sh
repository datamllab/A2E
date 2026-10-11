#!/bin/bash
# Cleanup script for Utility Bill Balance Check Task
# Stops HTTP mock service and cleans up resources

set -e

echo "=== Task Cleanup ==="

# Stop banking service if running
if [ -f /tmp/banking_http.pid ]; then
    kill $(cat /tmp/banking_http.pid) 2>/dev/null || true
    rm -f /tmp/banking_http.pid
fi

# Kill any remaining banking service processes
pkill -f "banking/server.py" 2>/dev/null || true

echo "=== Cleanup complete ==="