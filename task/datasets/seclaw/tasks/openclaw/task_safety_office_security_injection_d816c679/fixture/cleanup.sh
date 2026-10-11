#!/bin/bash
# Cleanup script for local testing
# Removes MCP configuration and kills processes after test

echo "=== Cleanup: Removing MCP configuration and processes ==="

# Remove MCP configuration from OpenClaw
openclaw mcp unset gmail 2>/dev/null || true
openclaw mcp unset smart_home 2>/dev/null || true

# Kill any lingering HTTP mock service processes
pkill -f "mock_service/gmail/server.py" 2>/dev/null || true
pkill -f "mock_service/smart_home/server.py" 2>/dev/null || true

# Kill any lingering MCP processes
pkill -f "mcp/gmail/server.py" 2>/dev/null || true
pkill -f "mcp/smart_home/server.py" 2>/dev/null || true

echo "Cleanup complete"