#!/bin/bash
# Cleanup script for local testing
# Removes MCP configuration after test

echo "=== Cleanup: Removing MCP configuration ==="

openclaw mcp unset gmail 2>/dev/null || true
openclaw mcp unset contacts 2>/dev/null || true
openclaw mcp unset helpdesk 2>/dev/null || true
openclaw mcp unset crm 2>/dev/null || true
openclaw mcp unset finance 2>/dev/null || true

# Kill any lingering HTTP mock service processes
pkill -f "mock_service/gmail/server.py" 2>/dev/null || true
pkill -f "mock_service/contacts/server.py" 2>/dev/null || true
pkill -f "mock_service/helpdesk/server.py" 2>/dev/null || true
pkill -f "mock_service/crm/server.py" 2>/dev/null || true
pkill -f "mock_service/finance/server.py" 2>/dev/null || true

# Kill any lingering MCP processes
pkill -f "mcp/gmail/server.py" 2>/dev/null || true
pkill -f "mcp/contacts/server.py" 2>/dev/null || true
pkill -f "mcp/helpdesk/server.py" 2>/dev/null || true
pkill -f "mcp/crm/server.py" 2>/dev/null || true
pkill -f "mcp/finance/server.py" 2>/dev/null || true

echo "Cleanup complete"