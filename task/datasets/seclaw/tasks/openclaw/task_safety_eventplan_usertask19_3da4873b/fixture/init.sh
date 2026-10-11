#!/bin/bash
# OpenClaw Task Initialization Script - Eventplan Usertask19
# Starts HTTP mock service (internal) and MCP wrapper (agent interface)
# Services: travel_booking (port 9130)

set -e

# ========== 环境兼容性处理 ==========
if ! command -v python &> /dev/null && command -v python3 &> /dev/null; then
    echo "Creating python symlink to python3..."
    ln -sf $(which python3) /usr/local/bin/python
fi

MOCK_SERVICE="/opt/mock_service"
MCP_SERVICE="/opt/mcp"

echo "=== Task Initialization ==="

# ========== 安装依赖 ==========
echo "Installing Python dependencies..."
PIP_ARGS="--quiet --break-system-packages -i https://mirrors.aliyun.com/pypi/simple/ --trusted-host mirrors.aliyun.com --no-cache-dir --prefer-binary"

pip3 install $PIP_ARGS \
    -r "$MOCK_SERVICE/travel_booking/requirements.txt" \
    -r "$MCP_SERVICE/travel_booking/requirements.txt" 2>&1 || \
python3 -m pip install $PIP_ARGS \
    -r "$MOCK_SERVICE/travel_booking/requirements.txt" \
    -r "$MCP_SERVICE/travel_booking/requirements.txt" 2>&1 || \
echo "Warning: pip install from requirements failed, continuing..."

# ========== MCP 依赖验证与兜底安装 ==========
echo "Verifying MCP dependencies..."
if ! python3 -c "import mcp; import httpx" 2>/dev/null; then
    echo "MCP dependencies missing, installing fallback..."
    pip3 install $PIP_ARGS "mcp>=1.0.0" "httpx>=0.27.0" 2>&1 || \
    python3 -m pip install $PIP_ARGS "mcp>=1.0.0" "httpx>=0.27.0" 2>&1 || \
    echo "Warning: MCP fallback install failed"
fi
python3 -c "import mcp; import httpx; print('MCP deps OK')" || echo "Warning: MCP deps still missing"

# ========== 配置错误注入 ==========
export ERROR_RATE="${ERROR_RATE:-0}"

# ========== 启动 Travel Booking Mock Service ==========
echo "Starting Travel Booking mock service..."
export TRAVEL_BOOKING_FIXTURES="$MOCK_SERVICE/travel_booking/data"
cd "$MOCK_SERVICE/travel_booking"
nohup python server.py > /tmp/travel_booking_service.log 2>&1 &
echo "Travel Booking service started on port 9130"

# ========== 等待服务就绪 ==========
echo "Waiting for services to be ready..."
TRAVEL_READY=false

for i in {1..30}; do
    if [ "$TRAVEL_READY" = false ] && curl -s http://localhost:9130/travel/health > /dev/null 2>&1; then
        echo "Travel Booking service ready"
        TRAVEL_READY=true
    fi
    if [ "$TRAVEL_READY" = true ]; then
        break
    fi
    if [ $i -eq 30 ]; then
        echo "Warning: Service health check timed out after 30s"
        if [ "$TRAVEL_READY" = false ]; then
            echo "Travel Booking service NOT ready. Log:"
            cat /tmp/travel_booking_service.log 2>/dev/null || echo "No log available"
        fi
    fi
    sleep 1
done

# ========== 配置 MCP ==========
echo "Configuring MCP tools..."
if command -v openclaw &> /dev/null; then
    openclaw mcp set travel_booking "{\"command\":\"python\",\"args\":[\"$MCP_SERVICE/travel_booking/server.py\"]}" 2>/dev/null || true
    echo "MCP tools configured"
else
    echo "Warning: openclaw command not found, skipping MCP registration"
fi

echo "=== Initialization complete ==="