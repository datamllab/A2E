#!/bin/bash
# Cleanup script for local testing
# Removes MCP configuration after test

echo "=== Cleanup: Removing MCP configuration ==="

# Remove MCP configuration from OpenClaw
openclaw mcp unset banking 2>/dev/null || true

# Kill any lingering HTTP mock service processes
pkill -f "mock_service/banking/server.py" 2>/dev/null || true

# Kill any lingering MCP processes
pkill -f "mcp/banking/server.py" 2>/dev/null || true

echo "Cleanup complete"