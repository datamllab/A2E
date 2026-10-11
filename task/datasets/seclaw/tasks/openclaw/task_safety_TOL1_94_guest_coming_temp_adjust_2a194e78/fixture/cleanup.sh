#!/bin/bash
# Cleanup local test environment

echo "Cleaning up MCP configurations..."

# Remove MCP configurations (global in ~/.openclaw/openclaw.json)
openclaw mcp unset smart_home 2>/dev/null || true
echo "MCP configurations removed"

# Stop HTTP mock service processes
echo "Stopping mock service processes..."
pkill -f "mock_service/smart_home/server.py" 2>/dev/null || true

# Stop MCP processes
pkill -f "mcp/smart_home/server.py" 2>/dev/null || true
echo "Processes stopped"

echo "Cleanup complete"