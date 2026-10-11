#!/bin/bash
# OpenClaw Task Initialization Script
# Starts HTTP mock services (internal) and MCP wrappers (agent interface)
# v2: Improved error handling, dependency verification, and health checks

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
INSTALL_SUCCESS=false
pip3 install --quiet --break-system-packages \
    -i https://mirrors.aliyun.com/pypi/simple/ \
    --trusted-host mirrors.aliyun.com \
    --no-cache-dir \
    -r "$MOCK_SERVICE/gmail/requirements.txt" \
    -r "$MOCK_SERVICE/smart_home/requirements.txt" \
    -r "$MCP_SERVICE/gmail/requirements.txt" \
    -r "$MCP_SERVICE/smart_home/requirements.txt" 2>&1 && INSTALL_SUCCESS=true

if [ "$INSTALL_SUCCESS" = false ]; then
    echo "pip3 install failed, trying python3 -m pip..."
    python3 -m pip install --quiet --break-system-packages \
        -i https://mirrors.aliyun.com/pypi/simple/ \
        --trusted-host mirrors.aliyun.com \
        --no-cache-dir \
        -r "$MOCK_SERVICE/gmail/requirements.txt" \
        -r "$MOCK_SERVICE/smart_home/requirements.txt" \
        -r "$MCP_SERVICE/gmail/requirements.txt" \
        -r "$MCP_SERVICE/smart_home/requirements.txt" 2>&1 && INSTALL_SUCCESS=true
fi

if [ "$INSTALL_SUCCESS" = false ]; then
    echo "ERROR: Failed to install Python dependencies" >&2
    exit 1
fi

# ========== 验证关键依赖 ==========
echo "Verifying critical Python dependencies..."
python3 -c "import fastapi; import uvicorn; import pydantic; import httpx" 2>&1 || {
    echo "ERROR: Core mock service dependencies (fastapi, uvicorn, pydantic, httpx) not available" >&2
    exit 1
}
python3 -c "import mcp; from mcp.server import Server; from mcp.server.stdio import stdio_server; from mcp.types import Tool, TextContent" 2>&1 || {
    echo "ERROR: MCP SDK dependencies not available" >&2
    exit 1
}
echo "Dependencies verified OK"

# ========== 启动 Gmail mock service ==========
echo "Starting Gmail mock service..."
export GMAIL_FIXTURES="$MOCK_SERVICE/gmail/data/inbox.json"
cd "$MOCK_SERVICE/gmail"
nohup python server.py > /tmp/gmail_mock.log 2>&1 &
GMAIL_PID=$!
echo "$GMAIL_PID" > /tmp/gmail_mock.pid

GMAIL_READY=false
for i in {1..30}; do
    if curl -s http://localhost:9100/gmail/health > /dev/null 2>&1; then
        echo "Gmail mock service ready (port 9100, PID $GMAIL_PID)"
        GMAIL_READY=true
        break
    fi
    sleep 1
done

if [ "$GMAIL_READY" = false ]; then
    echo "ERROR: Gmail mock service failed to start within 30 seconds" >&2
    echo "--- Gmail mock service log ---" >&2
    cat /tmp/gmail_mock.log >&2 2>/dev/null || true
    echo "--- End log ---" >&2
    exit 1
fi

# ========== 启动 Smart Home mock service ==========
echo "Starting Smart Home mock service..."
export SMART_HOME_FIXTURES="$MOCK_SERVICE/smart_home/data/devices.json"
cd "$MOCK_SERVICE/smart_home"
nohup python server.py > /tmp/smart_home_mock.log 2>&1 &
SMART_HOME_PID=$!
echo "$SMART_HOME_PID" > /tmp/smart_home_mock.pid

SMART_HOME_READY=false
for i in {1..30}; do
    if curl -s http://localhost:9120/smart-home/health > /dev/null 2>&1; then
        echo "Smart Home mock service ready (port 9120, PID $SMART_HOME_PID)"
        SMART_HOME_READY=true
        break
    fi
    sleep 1
done

if [ "$SMART_HOME_READY" = false ]; then
    echo "ERROR: Smart Home mock service failed to start within 30 seconds" >&2
    echo "--- Smart Home mock service log ---" >&2
    cat /tmp/smart_home_mock.log >&2 2>/dev/null || true
    echo "--- End log ---" >&2
    exit 1
fi

# ========== 配置 MCP ==========
echo "Configuring MCP tools..."
openclaw mcp set gmail "{\"command\":\"python\",\"args\":[\"$MCP_SERVICE/gmail/server.py\"]}" 2>/dev/null || {
    echo "WARNING: Failed to configure gmail MCP tool" >&2
}
openclaw mcp set smart_home "{\"command\":\"python\",\"args\":[\"$MCP_SERVICE/smart_home/server.py\"]}" 2>/dev/null || {
    echo "WARNING: Failed to configure smart_home MCP tool" >&2
}

# ========== 验证 MCP 注册 ==========
echo "Verifying MCP tool registration..."
MCP_VERIFIED=true
if ! openclaw mcp list 2>/dev/null | grep -q "gmail"; then
    echo "WARNING: gmail MCP tool not found in registration list" >&2
    MCP_VERIFIED=false
fi
if ! openclaw mcp list 2>/dev/null | grep -q "smart_home"; then
    echo "WARNING: smart_home MCP tool not found in registration list" >&2
    MCP_VERIFIED=false
fi
if [ "$MCP_VERIFIED" = true ]; then
    echo "MCP tools registered OK"
fi

echo "=== Initialization complete ==="