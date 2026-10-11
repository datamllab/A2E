#!/bin/bash
# Cleanup script for local testing
# Removes MCP configuration after test

echo "=== Cleanup: Removing MCP configuration ==="

openclaw mcp unset banking 2>/dev/null || true

pkill -f "mock_service/banking/server.py" 2>/dev/null || true

pkill -f "mcp/banking/server.py" 2>/dev/null || true

echo "Cleanup complete"
