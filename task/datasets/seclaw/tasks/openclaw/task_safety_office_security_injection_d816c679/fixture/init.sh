#!/bin/bash
# Office Security Email Injection Task - Initialization Script
# Starts HTTP mock services (internal) and MCP wrappers (agent interface)

set -e

# ========== 环境兼容性处理 ==========
if ! command -v python &> /dev/null && command -v python3 &> /dev/null; then
    echo "Creating python symlink to python3..."
    ln -sf $(which python3) /usr/local/bin/python
fi

MOCK_SERVICE="/opt/mock_service"
MCP_SERVICE="/opt/mcp"

echo "=== Office Security Injection Task Initialization ==="

# ========== 安装依赖 ==========
echo "Installing Python dependencies..."
pip3 install --quiet --break-system-packages \
    -i https://mirrors.aliyun.com/pypi/simple/ \
    --trusted-host mirrors.aliyun.com \
    --no-cache-dir \
    -r "$MOCK_SERVICE/gmail/requirements.txt" \
    -r "$MOCK_SERVICE/smart_home/requirements.txt" \
    -r "$MCP_SERVICE/gmail/requirements.txt" \
    -r "$MCP_SERVICE/smart_home/requirements.txt" 2>&1 || \
python3 -m pip install --quiet --break-system-packages \
    -i https://mirrors.aliyun.com/pypi/simple/ \
    --trusted-host mirrors.aliyun.com \
    --no-cache-dir \
    -r "$MOCK_SERVICE/gmail/requirements.txt" \
    -r "$MOCK_SERVICE/smart_home/requirements.txt" \
    -r "$MCP_SERVICE/gmail/requirements.txt" \
    -r "$MCP_SERVICE/smart_home/requirements.txt" 2>&1 || \
echo "Warning: pip install failed, continuing..."

# ========== 启动 Gmail HTTP Mock Service ==========
echo "Starting Gmail mock service..."
export GMAIL_FIXTURES="$MOCK_SERVICE/gmail/data/inbox.json"
cd "$MOCK_SERVICE/gmail"
PORT=9100 nohup python server.py > /tmp/gmail_http.log 2>&1 &
echo "Gmail service started with PID $!"

# ========== 启动 Smart Home HTTP Mock Service ==========
echo "Starting Smart Home mock service..."
export SMART_HOME_FIXTURES="$MOCK_SERVICE/smart_home/data/devices.json"
cd "$MOCK_SERVICE/smart_home"
PORT=9120 nohup python server.py > /tmp/smart_home_http.log 2>&1 &
echo "Smart Home service started with PID $!"

# ========== 等待服务就绪 ==========
echo "Waiting for Gmail service..."
for i in {1..30}; do
    if curl -s http://localhost:9100/gmail/health > /dev/null 2>&1; then
        echo "✓ Gmail service ready"
        break
    fi
    if [ $i -eq 30 ]; then
        echo "Warning: Gmail service health check timeout"
        tail -5 /tmp/gmail_http.log 2>/dev/null || echo "No log available"
    fi
    sleep 1
done

echo "Waiting for Smart Home service..."
for i in {1..30}; do
    if curl -s http://localhost:9120/smart-home/health > /dev/null 2>&1; then
        echo "✓ Smart Home service ready"
        break
    fi
    if [ $i -eq 30 ]; then
        echo "Warning: Smart Home service health check timeout"
        tail -5 /tmp/smart_home_http.log 2>/dev/null || echo "No log available"
    fi
    sleep 1
done

# ========== 配置 MCP ==========
echo "Configuring MCP tools..."
if command -v openclaw &> /dev/null; then
    openclaw mcp set gmail "{\"command\":\"python\",\"args\":[\"$MCP_SERVICE/gmail/server.py\"]}" 2>/dev/null || true
    echo "✓ Gmail MCP configured"
    openclaw mcp set smart_home "{\"command\":\"python\",\"args\":[\"$MCP_SERVICE/smart_home/server.py\"]}" 2>/dev/null || true
    echo "✓ Smart Home MCP configured"
else
    echo "Warning: openclaw command not found, skipping MCP registration"
fi

echo "=== Initialization complete ==="