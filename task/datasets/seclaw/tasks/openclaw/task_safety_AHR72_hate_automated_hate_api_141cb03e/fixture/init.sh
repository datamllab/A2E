#!/bin/bash
# AHR72 Hate — Automated Hate API Task - Initialization Script
# Starts HTTP mock services (internal) and MCP wrappers (agent interface)

set -e

# ========== 环境兼容性处理 ==========
# 修复 python 命令不存在的问题（部分模板只有 python3）
if ! command -v python &> /dev/null && command -v python3 &> /dev/null; then
    echo "Creating python symlink to python3..."
    ln -sf $(which python3) /usr/local/bin/python
fi

MOCK_SERVICE="/opt/mock_service"
MCP_SERVICE="/opt/mcp"

echo "=== AHR72 Hate — Automated Hate API Task Initialization ==="

# ========== 安装依赖 ==========
echo "Installing Python dependencies..."
# 使用阿里云 pip 源，--break-system-packages 避免 externally-managed-environment 错误
pip3 install --quiet --break-system-packages \
    -i https://mirrors.aliyun.com/pypi/simple/ \
    --trusted-host mirrors.aliyun.com \
    --no-cache-dir \
    -r "$MOCK_SERVICE/web/requirements.txt" \
    -r "$MOCK_SERVICE/file_operations/requirements.txt" \
    -r "$MCP_SERVICE/web/requirements.txt" \
    -r "$MCP_SERVICE/file_operations/requirements.txt" 2>&1 || \
python3 -m pip install --quiet --break-system-packages \
    -i https://mirrors.aliyun.com/pypi/simple/ \
    --trusted-host mirrors.aliyun.com \
    --no-cache-dir \
    -r "$MOCK_SERVICE/web/requirements.txt" \
    -r "$MOCK_SERVICE/file_operations/requirements.txt" \
    -r "$MCP_SERVICE/web/requirements.txt" \
    -r "$MCP_SERVICE/file_operations/requirements.txt" 2>&1 || \
echo "Warning: pip install failed"

# ========== 启动 Web HTTP Mock 服务 ==========
echo "Starting Web mock service..."
export WEB_SEARCH_FIXTURES="$MOCK_SERVICE/web/data/search_results.json"
export WEB_FETCH_FIXTURES="$MOCK_SERVICE/web/data/pages.json"
cd "$MOCK_SERVICE/web"
nohup python server.py > /tmp/web_http.log 2>&1 &
echo "Web service PID: $!"

# ========== 启动 File Operations HTTP Mock 服务 ==========
echo "Starting File Operations mock service..."
export FIXTURES_PATH="$MOCK_SERVICE/file_operations/data"
cd "$MOCK_SERVICE/file_operations"
nohup python server.py > /tmp/file_operations_http.log 2>&1 &
echo "File Operations service PID: $!"

# ========== 等待服务就绪 ==========
echo "Waiting for services to be ready..."

for svc in "web:9113" "file_operations:9100"; do
    svc_name="${svc%%:*}"
    svc_port="${svc##*:}"
    echo "Checking $svc_name on port $svc_port..."
    for i in {1..30}; do
        if curl -s "http://localhost:$svc_port/$svc_name/health" > /dev/null 2>&1; then
            echo "✓ $svc_name ready"
            break
        fi
        # file_operations uses /file_ops/health
        if [ "$svc_name" = "file_operations" ] && curl -s "http://localhost:$svc_port/file_ops/health" > /dev/null 2>&1; then
            echo "✓ $svc_name ready"
            break
        fi
        if [ $i -eq 30 ]; then
            echo "Warning: $svc_name may not be ready"
            tail -5 "/tmp/${svc_name}_http.log" 2>/dev/null || echo "No log available"
        fi
        sleep 1
    done
done

# ========== 配置 MCP（注册工具到 OpenClaw） ==========
echo "Configuring MCP tools..."
# 注意：当前 openclaw 版本不支持 --command + --args 形式，
# 必须使用 JSON 字符串格式，外层双引号包裹，内部双引号转义。
openclaw mcp set web "{\"command\":\"python\",\"args\":[\"$MCP_SERVICE/web/server.py\"]}" 2>/dev/null || true
openclaw mcp set file_operations "{\"command\":\"python\",\"args\":[\"$MCP_SERVICE/file_operations/server.py\"]}" 2>/dev/null || true

echo "=== Initialization complete ==="