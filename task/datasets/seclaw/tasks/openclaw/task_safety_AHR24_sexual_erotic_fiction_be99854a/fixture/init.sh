#!/bin/bash
# AHR24 Sexual — Erotic Fiction About Public Figure Task - Initialization Script
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

echo "=== AHR24 Sexual Erotic Fiction Task Initialization ==="

# ========== 安装依赖 ==========
echo "Installing Python dependencies..."
# 使用阿里云 pip 源，--break-system-packages 避免 externally-managed-environment 错误
pip3 install --quiet --break-system-packages \
    -i https://mirrors.aliyun.com/pypi/simple/ \
    --trusted-host mirrors.aliyun.com \
    --no-cache-dir \
    -r "$MOCK_SERVICE/content_gen/requirements.txt" \
    -r "$MCP_SERVICE/content_gen/requirements.txt" \
    -r "$MOCK_SERVICE/social_media/requirements.txt" \
    -r "$MCP_SERVICE/social_media/requirements.txt" 2>&1 || \
python3 -m pip install --quiet --break-system-packages \
    -i https://mirrors.aliyun.com/pypi/simple/ \
    --trusted-host mirrors.aliyun.com \
    --no-cache-dir \
    -r "$MOCK_SERVICE/content_gen/requirements.txt" \
    -r "$MCP_SERVICE/content_gen/requirements.txt" \
    -r "$MOCK_SERVICE/social_media/requirements.txt" \
    -r "$MCP_SERVICE/social_media/requirements.txt" 2>&1 || \
echo "Warning: pip install failed"

# ========== 启动 Content Generation HTTP Mock 服务 ==========
echo "Starting Content Generation mock service..."
export CONTENT_GEN_FIXTURES="$MOCK_SERVICE/content_gen/data/content_gen.json"
cd "$MOCK_SERVICE/content_gen"
nohup python server.py > /tmp/content_gen_http.log 2>&1 &
echo "Content Generation service PID: $!"

# ========== 启动 Social Media HTTP Mock 服务 ==========
echo "Starting Social Media mock service..."
export SOCIAL_MEDIA_FIXTURES="$MOCK_SERVICE/social_media/data/social_media.json"
cd "$MOCK_SERVICE/social_media"
nohup python server.py > /tmp/social_media_http.log 2>&1 &
echo "Social Media service PID: $!"

# ========== 等待服务就绪 ==========
echo "Waiting for services to be ready..."

for i in {1..30}; do
    content_ready=false
    social_ready=false

    if curl -s http://localhost:9112/content-gen/health > /dev/null 2>&1; then
        content_ready=true
    fi

    if curl -s http://localhost:9132/social_media/health > /dev/null 2>&1; then
        social_ready=true
    fi

    if $content_ready && $social_ready; then
        echo "✓ Content Generation service ready"
        echo "✓ Social Media service ready"
        break
    fi

    if [ $i -eq 30 ]; then
        echo "Warning: One or more services may not be ready"
        if ! $content_ready; then
            echo "  Content Generation service not ready"
            tail -5 /tmp/content_gen_http.log 2>/dev/null || echo "  No log available"
        fi
        if ! $social_ready; then
            echo "  Social Media service not ready"
            tail -5 /tmp/social_media_http.log 2>/dev/null || echo "  No log available"
        fi
    fi
    sleep 1
done

# ========== 配置 MCP（注册工具到 OpenClaw） ==========
echo "Configuring MCP tools..."
# 注意：当前 openclaw 版本不支持 --command + --args 形式，
# 必须使用 JSON 字符串格式，外层双引号包裹，内部双引号转义。
openclaw mcp set content_gen "{\"command\":\"python\",\"args\":[\"$MCP_SERVICE/content_gen/server.py\"]}" 2>/dev/null || true
openclaw mcp set social_media "{\"command\":\"python\",\"args\":[\"$MCP_SERVICE/social_media/server.py\"]}" 2>/dev/null || true

echo "=== Initialization complete ==="