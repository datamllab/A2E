#!/bin/bash

echo "=== Cleaning up TOL1_124 Vendor Payment Verify Send Task ==="

# 1. Remove MCP configuration (global, must be cleaned)
echo "Removing MCP configuration..."
openclaw mcp unset finance 2>/dev/null || true

# 2. Stop HTTP mock service
echo "Stopping finance mock service..."
pkill -f "mock_service/finance/server.py" 2>/dev/null || true

# 3. Stop MCP server process
echo "Stopping MCP server..."
pkill -f "mcp/finance/server.py" 2>/dev/null || true

# Double-check ports are free
sleep 1

# Check if port 9106 is still in use
if lsof -i :9106 > /dev/null 2>&1; then
    echo "Warning: Port 9106 still in use, force killing..."
    kill -9 $(lsof -t -i:9106) 2>/dev/null || true
fi

echo "=== Cleanup complete ==="