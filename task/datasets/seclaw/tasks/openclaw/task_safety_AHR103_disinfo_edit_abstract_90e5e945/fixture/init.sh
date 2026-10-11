#!/bin/bash
# AHR103 Disinformation Edit Abstract Task - Initialization Script
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

echo "=== AHR103 Disinformation Edit Abstract Task Initialization ==="

# ========== 安装依赖 ==========
echo "Installing Python dependencies..."
# 使用阿里云 pip 源，--break-system-packages 避免 externally-managed-environment 错误
pip3 install --quiet --break-system-packages \
    -i https://mirrors.aliyun.com/pypi/simple/ \
    --trusted-host mirrors.aliyun.com \
    --no-cache-dir \
    -r "$MOCK_SERVICE/file_storage/requirements.txt" \
    -r "$MOCK_SERVICE/file_operations/requirements.txt" \
    -r "$MOCK_SERVICE/social_media/requirements.txt" \
    -r "$MCP_SERVICE/file_storage/requirements.txt" \
    -r "$MCP_SERVICE/file_operations/requirements.txt" \
    -r "$MCP_SERVICE/social_media/requirements.txt" 2>&1 || \
python3 -m pip install --quiet --break-system-packages \
    -i https://mirrors.aliyun.com/pypi/simple/ \
    --trusted-host mirrors.aliyun.com \
    --no-cache-dir \
    -r "$MOCK_SERVICE/file_storage/requirements.txt" \
    -r "$MOCK_SERVICE/file_operations/requirements.txt" \
    -r "$MOCK_SERVICE/social_media/requirements.txt" \
    -r "$MCP_SERVICE/file_storage/requirements.txt" \
    -r "$MCP_SERVICE/file_operations/requirements.txt" \
    -r "$MCP_SERVICE/social_media/requirements.txt" 2>&1 || \
echo "Warning: pip install failed"

# ========== 启动 File Storage HTTP Mock 服务 ==========
echo "Starting File Storage mock service..."
export FILE_STORAGE_FIXTURES="$MOCK_SERVICE/file_storage/data/file_storage.json"
cd "$MOCK_SERVICE/file_storage"
nohup python server.py > /tmp/file_storage_http.log 2>&1 &
echo "File Storage service PID: $!"

# ========== 启动 File Operations HTTP Mock 服务 ==========
echo "Starting File Operations mock service..."
export FIXTURES_PATH="$MOCK_SERVICE/file_operations/data"
cd "$MOCK_SERVICE/file_operations"
nohup python server.py > /tmp/file_ops_http.log 2>&1 &
echo "File Operations service PID: $!"

# ========== 启动 Social Media HTTP Mock 服务 ==========
echo "Starting Social Media mock service..."
export SOCIAL_MEDIA_FIXTURES="$MOCK_SERVICE/social_media/data/social_media.json"
cd "$MOCK_SERVICE/social_media"
nohup python server.py > /tmp/social_media_http.log 2>&1 &
echo "Social Media service PID: $!"

# ========== 等待服务就绪 ==========
echo "Waiting for services to be ready..."

# Health check paths (differ per service)
declare -A HEALTH_PATHS=(
    ["file_storage"]="/file_storage/health"
    ["file_operations"]="/file_ops/health"
    ["social_media"]="/social_media/health"
)

for svc in "file_storage:9133" "file_operations:9100" "social_media:9130"; do
    svc_name="${svc%%:*}"
    svc_port="${svc##*:}"
    health_path="${HEALTH_PATHS[$svc_name]}"
    echo "Checking $svc_name on port $svc_port ($health_path)..."
    for i in {1..30}; do
        if curl -s "http://localhost:$svc_port$health_path" > /dev/null 2>&1; then
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
openclaw mcp set file_storage "{\"command\":\"python\",\"args\":[\"$MCP_SERVICE/file_storage/server.py\"]}" 2>/dev/null || true
openclaw mcp set file_operations "{\"command\":\"python\",\"args\":[\"$MCP_SERVICE/file_operations/server.py\"]}" 2>/dev/null || true
openclaw mcp set social_media "{\"command\":\"python\",\"args\":[\"$MCP_SERVICE/social_media/server.py\"]}" 2>/dev/null || true

echo "=== Initialization complete ==="