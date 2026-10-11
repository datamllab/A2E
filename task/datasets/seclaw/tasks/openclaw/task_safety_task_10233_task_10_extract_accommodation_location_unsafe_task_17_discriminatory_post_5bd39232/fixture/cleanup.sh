#!/bin/bash
# Cleanup script for DingTalk/Slack task
# Stops mock service processes

echo "=== Cleaning up DingTalk/Slack task ==="

# Stop HTTP mock service
if [ -f /tmp/slack_http.pid ]; then
    kill $(cat /tmp/slack_http.pid) 2>/dev/null || true
    rm -f /tmp/slack_http.pid
fi

# Kill any remaining server processes on port 9101
pkill -f "python server.py" 2>/dev/null || true

echo "=== Cleanup complete ==="