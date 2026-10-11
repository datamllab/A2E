#!/bin/bash
# Cleanup script for slack mock service
pkill -f "python server.py" 2>/dev/null || true
echo "Services cleaned up"