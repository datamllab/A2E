#!/bin/bash
# Cleanup script for Smart Home Social Proof task

# Kill HTTP mock services
pkill -f "smart_home/server.py" 2>/dev/null || true
pkill -f "gmail/server.py" 2>/dev/null || true

echo "=== Cleanup complete ==="