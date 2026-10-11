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

echo "=== Task Initialization ==="

# ========== 安装依赖 ==========
echo "Installing Python dependencies..."
# 使用阿里云 pip 源，--break-system-packages 避免 externally-managed-environment 错误
pip3 install --quiet --break-system-packages \
    -i https://mirrors.aliyun.com/pypi/simple/ \
    --trusted-host mirrors.aliyun.com \
    --no-cache-dir \
    -r "$MOCK_SERVICE/code_editor/requirements.txt" \
    -r "$MCP_SERVICE/code_editor/requirements.txt" 2>&1 || \
python3 -m pip install --quiet --break-system-packages \
    -i https://mirrors.aliyun.com/pypi/simple/ \
    --trusted-host mirrors.aliyun.com \
    --no-cache-dir \
    -r "$MOCK_SERVICE/code_editor/requirements.txt" \
    -r "$MCP_SERVICE/code_editor/requirements.txt" 2>&1 || \
echo "Warning: pip install failed"

# ========== 启动服务 ==========
echo "Starting mock service..."
export CODE_EDITOR_FIXTURES="$MOCK_SERVICE/code_editor/data"
cd "$MOCK_SERVICE/code_editor"
nohup python server.py > /tmp/service.log 2>&1 &
echo "Service started"

# 等待服务就绪
for i in {1..30}; do
    if curl -s http://localhost:9101/code_editor/health > /dev/null 2>&1; then
        echo "✓ Service ready"
        break
    fi
    sleep 1
done

# ========== 配置 MCP ==========
echo "Configuring MCP tools..."
# 注意：当前 openclaw 版本不支持 --command + --args 形式，
# 必须使用 JSON 字符串格式，外层双引号包裹，内部双引号转义。
openclaw mcp set code_editor "{\"command\":\"python\",\"args\":[\"$MCP_SERVICE/code_editor/server.py\"]}" 2>/dev/null || true

# ========== 文件可达性保障 ==========
# Ensure legacy_code.txt is accessible from /opt/workspace/ so that both
# MCP read_file and OpenClaw built-in read tool can find it.
if [ -f /opt/local_files/legacy_code.txt ] && [ ! -f /opt/workspace/legacy_code.txt ]; then
    echo "Linking legacy_code.txt to workspace..."
    ln -sf /opt/local_files/legacy_code.txt /opt/workspace/legacy_code.txt
fi

echo "=== Initialization complete ==="
