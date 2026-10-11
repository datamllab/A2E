#!/bin/bash
# TOL1_124 Vendor Payment Verify Send Task - Initialization Script
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

echo "=== TOL1_124 Vendor Payment Verify Send Task Initialization ==="

# ========== 安装依赖 ==========
echo "Installing Python dependencies..."
# 使用阿里云 pip 源，--break-system-packages 避免 externally-managed-environment 错误
pip3 install --quiet --break-system-packages \
    -i https://mirrors.aliyun.com/pypi/simple/ \
    --trusted-host mirrors.aliyun.com \
    --no-cache-dir \
    -r "$MOCK_SERVICE/finance/requirements.txt" \
    -r "$MCP_SERVICE/finance/requirements.txt" 2>&1 || \
python3 -m pip install --quiet --break-system-packages \
    -i https://mirrors.aliyun.com/pypi/simple/ \
    --trusted-host mirrors.aliyun.com \
    --no-cache-dir \
    -r "$MOCK_SERVICE/finance/requirements.txt" \
    -r "$MCP_SERVICE/finance/requirements.txt" 2>&1 || \
echo "Warning: pip install failed"

# ========== 验证关键依赖 ==========
echo "Verifying critical Python packages..."
python3 -c "import fastapi; import uvicorn; import httpx; import mcp" 2>&1 || \
echo "Warning: Some critical packages may not be installed correctly"

# ========== 启动 HTTP Mock Service（内部，Agent 不直接感知） ==========
echo "Starting finance mock service..."
export FINANCE_FIXTURES="$MOCK_SERVICE/finance/data/finance.json"
export PORT=9106
cd "$MOCK_SERVICE/finance"
nohup python3 server.py > /tmp/finance_http.log 2>&1 &
HTTP_PID=$!
echo "HTTP service PID: $HTTP_PID"

# 等待服务就绪
echo "Waiting for finance service..."
for i in {1..30}; do
    if curl -s http://localhost:9106/finance/health > /dev/null 2>&1; then
        echo "Finance service ready on port 9106"
        break
    fi
    if [ $i -eq 30 ]; then
        echo "Warning: Finance service may not be ready"
        tail -5 /tmp/finance_http.log 2>/dev/null || echo "No log available"
    fi
    sleep 1
done

# ========== 配置 MCP（注册工具到 OpenClaw） ==========
echo "Configuring MCP tools..."
# 注意：当前 openclaw 版本不支持 --command + --args 形式，
# 必须使用 JSON 字符串格式，外层双引号包裹，内部双引号转义。
# 使用 python3 避免环境差异导致 python 命令不可用
PYTHON_PATH=$(which python3 2>/dev/null || which python 2>/dev/null || echo "python3")
openclaw mcp set finance "{\"command\":\"$PYTHON_PATH\",\"args\":[\"$MCP_SERVICE/finance/server.py\"]}" 2>&1
echo "MCP finance server configured with: $PYTHON_PATH $MCP_SERVICE/finance/server.py"

# ========== 验证 MCP Server 可启动 ==========
echo "Verifying MCP server can start..."
timeout 5 "$PYTHON_PATH" "$MCP_SERVICE/finance/server.py" --help 2>/dev/null || true
# MCP server 通过 stdio 通信，无法直接健康检查，但确认进程能启动即可
echo "MCP server startup check done"

echo "=== Initialization complete ==="