#!/bin/bash
# OpenClaw Task Initialization Script
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
SERVICE_NAME="file_operations"
PORT=9101

echo "=== Task Initialization ==="

# ========== 安装依赖 ==========
echo "Installing Python dependencies..."
# 使用阿里云 pip 源，--break-system-packages 避免 externally-managed-environment 错误
pip3 install --quiet --break-system-packages \
    -i https://mirrors.aliyun.com/pypi/simple/ \
    --trusted-host mirrors.aliyun.com \
    --no-cache-dir \
    -r "$MOCK_SERVICE/$SERVICE_NAME/requirements.txt" \
    -r "$MCP_SERVICE/$SERVICE_NAME/requirements.txt" 2>&1 || \
python3 -m pip install --quiet --break-system-packages \
    -i https://mirrors.aliyun.com/pypi/simple/ \
    --trusted-host mirrors.aliyun.com \
    --no-cache-dir \
    -r "$MOCK_SERVICE/$SERVICE_NAME/requirements.txt" \
    -r "$MCP_SERVICE/$SERVICE_NAME/requirements.txt" 2>&1 || \
echo "Warning: pip install failed"

# ========== 启动服务 ==========
echo "Starting mock service..."
export FILE_OPS_FIXTURES="$MOCK_SERVICE/$SERVICE_NAME/data"
export PORT=$PORT
cd "$MOCK_SERVICE/$SERVICE_NAME"
nohup python server.py > /tmp/file_operations.log 2>&1 &
echo "Service started on port $PORT"

# 等待服务就绪
for i in {1..30}; do
    if curl -s http://localhost:$PORT/file_ops/health > /dev/null 2>&1; then
        echo "Mock service ready"
        break
    fi
    if [ $i -eq 30 ]; then
        echo "Warning: Service health check timed out"
        echo "Service log:"
        cat /tmp/file_operations.log 2>/dev/null || echo "No log available"
    fi
    sleep 1
done

# ========== 配置 MCP ==========
echo "Configuring MCP tools..."
# 注意：当前 openclaw 版本不支持 --command + --args 形式，
# 必须使用 JSON 字符串格式，外层双引号包裹，内部双引号转义。
openclaw mcp set "$SERVICE_NAME" "{\"command\":\"python\",\"args\":[\"$MCP_SERVICE/$SERVICE_NAME/server.py\"]}" 2>/dev/null || true

echo "=== Initialization complete ==="