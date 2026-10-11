#!/bin/bash
# Password Manager Injection Task - Initialization Script
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

echo "=== Password Manager Injection Task Initialization ==="

# ========== 安装依赖 ==========
echo "Installing Python dependencies..."
# 使用阿里云 pip 源，--break-system-packages 避免 externally-managed-environment 错误
pip3 install --quiet --break-system-packages \
    -i https://mirrors.aliyun.com/pypi/simple/ \
    --trusted-host mirrors.aliyun.com \
    --no-cache-dir \
    -r "$MOCK_SERVICE/password_manager/requirements.txt" \
    -r "$MCP_SERVICE/password_manager/requirements.txt" 2>&1 || \
python3 -m pip install --quiet --break-system-packages \
    -i https://mirrors.aliyun.com/pypi/simple/ \
    --trusted-host mirrors.aliyun.com \
    --no-cache-dir \
    -r "$MOCK_SERVICE/password_manager/requirements.txt" \
    -r "$MCP_SERVICE/password_manager/requirements.txt" 2>&1 || \
echo "Warning: pip install failed, continuing..."

# ========== 启动 HTTP Mock Service ==========
echo "Starting internal password manager service..."
export PASSWORD_MANAGER_FIXTURES="$MOCK_SERVICE/password_manager/data/password.json"
cd "$MOCK_SERVICE/password_manager"
PORT=9133 nohup python server.py > /tmp/password_manager_http.log 2>&1 &
echo "HTTP service started with PID $!"

# 等待服务就绪
echo "Waiting for HTTP service..."
for i in {1..30}; do
    if curl -s http://localhost:9133/password_manager/health > /dev/null 2>&1; then
        echo "✓ HTTP service ready"
        break
    fi
    if [ $i -eq 30 ]; then
        echo "Warning: HTTP service health check timeout"
        echo "Service log:"
        tail -5 /tmp/password_manager_http.log 2>/dev/null || echo "No log available"
    fi
    sleep 1
done

# ========== 配置 MCP ==========
echo "Configuring MCP tools..."
# 注意：当前 openclaw 版本不支持 --command + --args 形式，
# 必须使用 JSON 字符串格式，外层双引号包裹，内部双引号转义。
if command -v openclaw &> /dev/null; then
    openclaw mcp set password_manager "{\"command\":\"python\",\"args\":[\"$MCP_SERVICE/password_manager/server.py\"]}" 2>/dev/null || true
    echo "✓ MCP configured"
else
    echo "Warning: openclaw command not found, skipping MCP registration"
fi

echo "=== Initialization complete ==="