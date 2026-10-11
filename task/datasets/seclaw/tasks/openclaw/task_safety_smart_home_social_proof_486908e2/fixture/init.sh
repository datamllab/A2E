#!/bin/bash
# Smart Home Social Proof Injection Defense Task - Initialization Script
# Starts HTTP mock services (internal) and MCP wrappers (agent interface)

set -e

# ========== 环境兼容性处理 ==========
if ! command -v python &> /dev/null && command -v python3 &> /dev/null; then
    echo "Creating python symlink to python3..."
    ln -sf $(which python3) /usr/local/bin/python
fi

MOCK_SERVICE="/opt/mock_service"
MCP_SERVICE="/opt/mcp"

echo "=== Smart Home Social Proof Task Initialization ==="

# ========== 安装依赖 ==========
echo "Installing Python dependencies..."
pip3 install --quiet --break-system-packages \
    -i https://mirrors.aliyun.com/pypi/simple/ \
    --trusted-host mirrors.aliyun.com \
    --no-cache-dir \
    -r "$MOCK_SERVICE/smart_home/requirements.txt" \
    -r "$MOCK_SERVICE/gmail/requirements.txt" \
    -r "$MCP_SERVICE/smart_home/requirements.txt" \
    -r "$MCP_SERVICE/gmail/requirements.txt" 2>&1 || \
python3 -m pip install --quiet --break-system-packages \
    -i https://mirrors.aliyun.com/pypi/simple/ \
    --trusted-host mirrors.aliyun.com \
    --no-cache-dir \
    -r "$MOCK_SERVICE/smart_home/requirements.txt" \
    -r "$MOCK_SERVICE/gmail/requirements.txt" \
    -r "$MCP_SERVICE/smart_home/requirements.txt" \
    -r "$MCP_SERVICE/gmail/requirements.txt" 2>&1 || \
echo "Warning: pip install failed"

# ========== 启动 Smart Home HTTP Mock 服务 ==========
echo "Starting smart_home mock service..."
export SMART_HOME_FIXTURES="$MOCK_SERVICE/smart_home/data/smart_home.json"
export PORT=9116
cd "$MOCK_SERVICE/smart_home"
nohup python server.py > /tmp/smart_home_http.log 2>&1 &
SMART_HOME_PID=$!
echo "Smart Home HTTP service PID: $SMART_HOME_PID"

# 等待 Smart Home 服务就绪
echo "Waiting for Smart Home HTTP service..."
for i in {1..30}; do
    if curl -s http://localhost:9116/smart-home/health > /dev/null 2>&1; then
        echo "✓ Smart Home service ready"
        break
    fi
    if [ $i -eq 30 ]; then
        echo "Warning: Smart Home HTTP service may not be ready"
        tail -5 /tmp/smart_home_http.log 2>/dev/null || echo "No log available"
    fi
    sleep 1
done

# ========== 启动 Gmail HTTP Mock 服务 ==========
echo "Starting gmail mock service..."
export GMAIL_FIXTURES="$MOCK_SERVICE/gmail/data/inbox.json"
export PORT=9117
cd "$MOCK_SERVICE/gmail"
nohup python server.py > /tmp/gmail_http.log 2>&1 &
GMAIL_PID=$!
echo "Gmail HTTP service PID: $GMAIL_PID"

# 等待 Gmail 服务就绪
echo "Waiting for Gmail HTTP service..."
for i in {1..30}; do
    if curl -s http://localhost:9117/gmail/health > /dev/null 2>&1; then
        echo "✓ Gmail service ready"
        break
    fi
    if [ $i -eq 30 ]; then
        echo "Warning: Gmail HTTP service may not be ready"
        tail -5 /tmp/gmail_http.log 2>/dev/null || echo "No log available"
    fi
    sleep 1
done

# ========== 配置 MCP（注册工具到 OpenClaw） ==========
echo "Configuring MCP tools..."
openclaw mcp set smart_home "{\"command\":\"python\",\"args\":[\"$MCP_SERVICE/smart_home/server.py\"]}" 2>/dev/null || true
openclaw mcp set gmail "{\"command\":\"python\",\"args\":[\"$MCP_SERVICE/gmail/server.py\"]}" 2>/dev/null || true

echo "=== Initialization complete ==="