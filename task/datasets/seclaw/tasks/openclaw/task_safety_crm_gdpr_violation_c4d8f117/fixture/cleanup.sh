#!/bin/bash
# Cleanup script for local testing

# Remove MCP configurations
echo "Removing MCP configurations..."
openclaw mcp unset crm 2>/dev/null || true

# Stop mock service processes
echo "Stopping mock services..."
pkill -f "mock_service/crm/server.py" 2>/dev/null || true

# Stop MCP processes
pkill -f "mcp/crm/server.py" 2>/dev/null || true

echo "Cleanup complete"