#!/bin/bash
# Cleanup script for local testing
# Removes MCP configuration after test

echo "=== Cleanup: Removing MCP configuration ==="

# Remove MCP configuration from OpenClaw
openclaw mcp unset password_manager 2>/dev/null || true

# Kill any lingering HTTP mock service processes
pkill -f "mock_service/password_manager/server.py" 2>/dev/null || true

# Kill any lingering MCP processes
pkill -f "mcp/password_manager/server.py" 2>/dev/null || true

echo "Cleanup complete"