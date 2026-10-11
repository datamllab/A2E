#!/bin/bash
# Cleanup script for file_storage and social_media mock services
pkill -f "python server.py" 2>/dev/null || true
echo "Services cleaned up"