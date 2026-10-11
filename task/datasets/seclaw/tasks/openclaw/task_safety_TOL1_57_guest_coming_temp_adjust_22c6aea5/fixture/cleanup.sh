#!/bin/bash
# Cleanup script for smart_home mock service
pkill -f "python server.py" 2>/dev/null || true
echo "Services cleaned up"