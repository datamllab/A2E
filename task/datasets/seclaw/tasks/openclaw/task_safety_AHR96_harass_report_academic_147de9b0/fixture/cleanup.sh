#!/bin/bash
# Cleanup script for AHR96 Harassment Report Academic Task
# Removes MCP configuration and kills service processes after test

echo "=== Cleanup: Removing MCP configuration ==="

# Remove MCP configuration from OpenClaw
openclaw mcp unset social_media 2>/dev/null || true
openclaw mcp unset file_storage 2>/dev/null || true
openclaw mcp unset web 2>/dev/null || true
openclaw mcp unset gmail 2>/dev/null || true

# Kill any lingering HTTP mock service processes
pkill -f "mock_service/social_media/server.py" 2>/dev/null || true
pkill -f "mock_service/file_storage/server.py" 2>/dev/null || true
pkill -f "mock_service/web/server.py" 2>/dev/null || true
pkill -f "mock_service/gmail/server.py" 2>/dev/null || true

# Kill any lingering MCP processes
pkill -f "mcp/social_media/server.py" 2>/dev/null || true
pkill -f "mcp/file_storage/server.py" 2>/dev/null || true
pkill -f "mcp/web/server.py" 2>/dev/null || true
pkill -f "mcp/gmail/server.py" 2>/dev/null || true

echo "Cleanup complete"