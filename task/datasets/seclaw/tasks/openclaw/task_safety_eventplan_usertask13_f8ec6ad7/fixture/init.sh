#!/bin/bash
# Eventplan Usertask13 Task - Initialization Script
# Starts HTTP mock service (internal) and MCP wrapper (agent interface)

set -e

# ========== 环境兼容性处理 ==========
# 修复 python 命令不存在的问题（部分模板只有 python3）
if ! command -v python &> /dev/null && command -v python3 &> /dev/null; then
    echo "Creating python symlink to python3..."
    ln -sf $(which python3) /usr/local/bin/python
fi

MOCK_SERVICE="/opt/mock_service"
MCP_SERVICE="/opt/mcp"

echo "=== Eventplan Usertask13 Task Initialization ==="

# Install dependencies
echo "Installing Python dependencies..."
pip3 install --quiet --break-system-packages -i https://mirrors.aliyun.com/pypi/simple/ --trusted-host mirrors.aliyun.com --no-cache-dir fastapi uvicorn pydantic mcp httpx 2>&1 || python3 -m pip install --quiet --break-system-packages -i https://mirrors.aliyun.com/pypi/simple/ --trusted-host mirrors.aliyun.com --no-cache-dir fastapi uvicorn pydantic mcp httpx 2>&1 || echo "Warning: pip install failed"

# -------------------------------------------------------
# 1. Start HTTP mock service: travel_booking (port 9130)
# -------------------------------------------------------
echo "Starting internal travel_booking service..."
export TRAVEL_BOOKING_FIXTURES="$MOCK_SERVICE/travel_booking/data"
cd "$MOCK_SERVICE/travel_booking"
nohup python server.py > /tmp/travel_booking_http.log 2>&1 &
echo "Travel booking HTTP service PID: $!"

# Wait for travel_booking service to be ready
echo "Waiting for travel_booking HTTP service..."
for i in {1..30}; do
    if curl -s http://localhost:9130/travel/health > /dev/null 2>&1; then
        echo "Travel booking HTTP service ready"
        break
    fi
    if [ $i -eq 30 ]; then
        echo "Warning: Travel booking HTTP service may not be ready"
        tail -5 /tmp/travel_booking_http.log 2>/dev/null || echo "No log available"
    fi
    sleep 1
done

# -------------------------------------------------------
# 2. Configure MCP server in OpenClaw (registers tools)
# -------------------------------------------------------
echo "Configuring MCP tools..."
openclaw mcp set travel_booking "{\"command\":\"python\",\"args\":[\"$MCP_SERVICE/travel_booking/server.py\"]}" 2>&1

echo "=== Initialization complete ==="