#!/bin/bash
# Cleanup script for local testing
# Removes MCP configuration and stops mock service processes

echo "=== Cleanup: Removing MCP configuration and stopping services ==="

# Remove MCP configuration from OpenClaw
openclaw mcp unset travel_booking 2>/dev/null || true

# Kill any lingering HTTP mock service processes
pkill -f "mock_service/travel_booking/server.py" 2>/dev/null || true

# Kill any lingering MCP processes
pkill -f "mcp/travel_booking/server.py" 2>/dev/null || true

echo "Cleanup complete"