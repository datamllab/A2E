#!/bin/bash

echo "=== Cleaning up Office Building Power Save task ==="

# 1. Remove MCP configuration
echo "Removing MCP configuration..."
openclaw mcp unset smart_home 2>/dev/null || true

# 2. Stop HTTP mock service process
echo "Stopping HTTP mock service..."
pkill -f "mock_service/smart_home/server.py" 2>/dev/null || true

# 3. Stop MCP server process
echo "Stopping MCP server..."
pkill -f "mcp/smart_home/server.py" 2>/dev/null || true

echo "=== Cleanup complete ==="