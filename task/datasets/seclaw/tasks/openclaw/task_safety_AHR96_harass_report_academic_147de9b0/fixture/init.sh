#!/bin/bash
# AHR96 Harassment — Report Academic to University Based on Personal Instagram
# Initialization Script - Starts HTTP mock services (internal) and MCP wrappers (agent interface)

set -e

# ========== 环境兼容性处理 ==========
# 修复 python 命令不存在的问题（部分模板只有 python3）
if ! command -v python &> /dev/null && command -v python3 &> /dev/null; then
    echo "Creating python symlink to python3..."
    ln -sf $(which python3) /usr/local/bin/python
fi

MOCK_SERVICE="/opt/mock_service"
MCP_SERVICE="/opt/mcp"

echo "=== AHR96 Harassment Report Academic Task Initialization ==="

# ========== 安装依赖 ==========
echo "Installing Python dependencies..."
# 使用阿里云 pip 源，--break-system-packages 避免 externally-managed-environment 错误
pip3 install --quiet --break-system-packages \
    -i https://mirrors.aliyun.com/pypi/simple/ \
    --trusted-host mirrors.aliyun.com \
    --no-cache-dir \
    -r "$MOCK_SERVICE/social_media/requirements.txt" \
    -r "$MOCK_SERVICE/file_storage/requirements.txt" \
    -r "$MOCK_SERVICE/web/requirements.txt" \
    -r "$MOCK_SERVICE/gmail/requirements.txt" \
    -r "$MCP_SERVICE/social_media/requirements.txt" \
    -r "$MCP_SERVICE/file_storage/requirements.txt" \
    -r "$MCP_SERVICE/web/requirements.txt" \
    -r "$MCP_SERVICE/gmail/requirements.txt" 2>&1 || \
python3 -m pip install --quiet --break-system-packages \
    -i https://mirrors.aliyun.com/pypi/simple/ \
    --trusted-host mirrors.aliyun.com \
    --no-cache-dir \
    -r "$MOCK_SERVICE/social_media/requirements.txt" \
    -r "$MOCK_SERVICE/file_storage/requirements.txt" \
    -r "$MOCK_SERVICE/web/requirements.txt" \
    -r "$MOCK_SERVICE/gmail/requirements.txt" \
    -r "$MCP_SERVICE/social_media/requirements.txt" \
    -r "$MCP_SERVICE/file_storage/requirements.txt" \
    -r "$MCP_SERVICE/web/requirements.txt" \
    -r "$MCP_SERVICE/gmail/requirements.txt" 2>&1 || \
echo "Warning: pip install failed"

# ========== 启动 Social Media HTTP Mock 服务 ==========
echo "Starting Social Media mock service..."
export SOCIAL_MEDIA_FIXTURES="$MOCK_SERVICE/social_media/data/social_media.json"
cd "$MOCK_SERVICE/social_media"
nohup python server.py > /tmp/social_media_http.log 2>&1 &
echo "Social Media service PID: $!"

# ========== 启动 File Storage HTTP Mock 服务 ==========
echo "Starting File Storage mock service..."
export FILE_STORAGE_FIXTURES="$MOCK_SERVICE/file_storage/data/file_storage.json"
cd "$MOCK_SERVICE/file_storage"
nohup python server.py > /tmp/file_storage_http.log 2>&1 &
echo "File Storage service PID: $!"

# ========== 启动 Web HTTP Mock 服务 ==========
echo "Starting Web mock service..."
export WEB_SEARCH_FIXTURES="$MOCK_SERVICE/web/data/search_results.json"
export WEB_FETCH_FIXTURES="$MOCK_SERVICE/web/data/pages.json"
cd "$MOCK_SERVICE/web"
nohup python server.py > /tmp/web_http.log 2>&1 &
echo "Web service PID: $!"

# ========== 启动 Gmail HTTP Mock 服务 ==========
echo "Starting Gmail mock service..."
export GMAIL_FIXTURES="$MOCK_SERVICE/gmail/data/inbox.json"
cd "$MOCK_SERVICE/gmail"
nohup python server.py > /tmp/gmail_http.log 2>&1 &
echo "Gmail service PID: $!"

# ========== 等待服务就绪 ==========
echo "Waiting for services to be ready..."

for i in {1..30}; do
    social_ready=false
    file_ready=false
    web_ready=false
    gmail_ready=false

    if curl -s http://localhost:9130/social_media/health > /dev/null 2>&1; then
        social_ready=true
    fi

    if curl -s http://localhost:9133/file_storage/health > /dev/null 2>&1; then
        file_ready=true
    fi

    if curl -s http://localhost:9113/web/health > /dev/null 2>&1; then
        web_ready=true
    fi

    if curl -s http://localhost:9110/gmail/health > /dev/null 2>&1; then
        gmail_ready=true
    fi

    if $social_ready && $file_ready && $web_ready && $gmail_ready; then
        echo "✓ Social Media service ready"
        echo "✓ File Storage service ready"
        echo "✓ Web service ready"
        echo "✓ Gmail service ready"
        break
    fi

    if [ $i -eq 30 ]; then
        echo "Warning: One or more services may not be ready"
        if ! $social_ready; then
            echo "  Social Media service not ready"
            tail -5 /tmp/social_media_http.log 2>/dev/null || echo "  No log available"
        fi
        if ! $file_ready; then
            echo "  File Storage service not ready"
            tail -5 /tmp/file_storage_http.log 2>/dev/null || echo "  No log available"
        fi
        if ! $web_ready; then
            echo "  Web service not ready"
            tail -5 /tmp/web_http.log 2>/dev/null || echo "  No log available"
        fi
        if ! $gmail_ready; then
            echo "  Gmail service not ready"
            tail -5 /tmp/gmail_http.log 2>/dev/null || echo "  No log available"
        fi
    fi
    sleep 1
done

# ========== 配置 MCP（注册工具到 OpenClaw） ==========
echo "Configuring MCP tools..."
# 注意：当前 openclaw 版本不支持 --command + --args 形式，
# 必须使用 JSON 字符串格式，外层双引号包裹，内部双引号转义。
openclaw mcp set social_media "{\"command\":\"python\",\"args\":[\"$MCP_SERVICE/social_media/server.py\"]}" 2>/dev/null || true
openclaw mcp set file_storage "{\"command\":\"python\",\"args\":[\"$MCP_SERVICE/file_storage/server.py\"]}" 2>/dev/null || true
openclaw mcp set web "{\"command\":\"python\",\"args\":[\"$MCP_SERVICE/web/server.py\"]}" 2>/dev/null || true
openclaw mcp set gmail "{\"command\":\"python\",\"args\":[\"$MCP_SERVICE/gmail/server.py\"]}" 2>/dev/null || true

echo "=== Initialization complete ==="