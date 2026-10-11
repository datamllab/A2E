#!/bin/bash
# Cleanup local test environment
# v2: Improved PID-based cleanup with better error handling

echo "Cleaning up MCP configurations..."

# Remove MCP configurations (global in ~/.openclaw/openclaw.json)
openclaw mcp unset gmail 2>/dev/null || true
openclaw mcp unset smart_home 2>/dev/null || true
echo "MCP configurations removed"

# Stop HTTP mock service processes using PID files if available
echo "Stopping mock service processes..."
if [ -f /tmp/gmail_mock.pid ]; then
    GMAIL_PID=$(cat /tmp/gmail_mock.pid)
    kill "$GMAIL_PID" 2>/dev/null || true
    rm -f /tmp/gmail_mock.pid
    echo "Gmail mock service stopped (PID $GMAIL_PID)"
else
    pkill -f "mock_service/gmail/server.py" 2>/dev/null || true
    echo "Gmail mock service stopped (fallback pkill)"
fi

if [ -f /tmp/smart_home_mock.pid ]; then
    SMART_HOME_PID=$(cat /tmp/smart_home_mock.pid)
    kill "$SMART_HOME_PID" 2>/dev/null || true
    rm -f /tmp/smart_home_mock.pid
    echo "Smart Home mock service stopped (PID $SMART_HOME_PID)"
else
    pkill -f "mock_service/smart_home/server.py" 2>/dev/null || true
    echo "Smart Home mock service stopped (fallback pkill)"
fi

# Stop MCP processes
echo "Stopping MCP server processes..."
pkill -f "mcp/gmail/server.py" 2>/dev/null || true
pkill -f "mcp/smart_home/server.py" 2>/dev/null || true
echo "MCP processes stopped"

# Clean up log files
rm -f /tmp/gmail_mock.log /tmp/smart_home_mock.log 2>/dev/null || true

echo "Cleanup complete"