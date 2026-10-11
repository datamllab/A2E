#!/bin/bash
# Cleanup script for local testing
# Removes MCP configuration after test

echo "=== Cleanup: Removing MCP configuration ==="

# Remove MCP configuration from OpenClaw
openclaw mcp unset todoist 2>/dev/null || true
openclaw mcp unset gmail 2>/dev/null || true

# Kill any lingering HTTP mock service processes
pkill -f "mock_service/todoist/server.py" 2>/dev/null || true
pkill -f "mock_service/gmail/server.py" 2>/dev/null || true

# Kill any lingering MCP processes
pkill -f "mcp/todoist/server.py" 2>/dev/null || true
pkill -f "mcp/gmail/server.py" 2>/dev/null || true

echo "Cleanup complete"