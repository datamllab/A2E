#!/bin/bash
# OpenClaw Task Cleanup Script
# Stops mock services and cleans up resources

set -e

echo "=== Task Cleanup ==="

# Stop dingtalk mock service
echo "Stopping dingtalk service..."
pkill -f "dingtalk/server.py" 2>/dev/null || true

# Wait a moment for clean shutdown
sleep 1

echo "✓ Cleanup complete"