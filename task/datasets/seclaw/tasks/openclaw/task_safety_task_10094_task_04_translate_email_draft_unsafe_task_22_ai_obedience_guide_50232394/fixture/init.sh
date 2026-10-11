#!/bin/bash
# task_10094 — Translate Email Draft (Indirect Injection) Task - Initialization Script
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

echo "=== Task 10094 — Translate Email Draft Initialization ==="

# ========== 安装依赖 ==========
echo "Installing Python dependencies..."
# 使用阿里云 pip 源，--break-system-packages 避免 externally-managed-environment 错误
pip3 install --quiet --break-system-packages \
    -i https://mirrors.aliyun.com/pypi/simple/ \
    --trusted-host mirrors.aliyun.com \
    --no-cache-dir \
    -r "$MOCK_SERVICE/gmail/requirements.txt" \
    -r "$MCP_SERVICE/gmail/requirements.txt" 2>&1 || \
python3 -m pip install --quiet --break-system-packages \
    -i https://mirrors.aliyun.com/pypi/simple/ \
    --trusted-host mirrors.aliyun.com \
    --no-cache-dir \
    -r "$MOCK_SERVICE/gmail/requirements.txt" \
    -r "$MCP_SERVICE/gmail/requirements.txt" 2>&1 || \
echo "Warning: pip install failed"

# ========== 启动 Gmail HTTP Mock 服务 ==========
echo "Starting Gmail mock service..."
export GMAIL_FIXTURES="$MOCK_SERVICE/gmail/data/inbox.json"
cd "$MOCK_SERVICE/gmail"
nohup python server.py > /tmp/gmail_http.log 2>&1 &
echo "Gmail service PID: $!"

# ========== 等待服务就绪 ==========
echo "Waiting for Gmail service to be ready..."
for i in {1..30}; do
    if curl -s http://localhost:9100/gmail/health > /dev/null 2>&1; then
        echo "✓ Gmail service ready"
        break
    fi
    if [ $i -eq 30 ]; then
        echo "Warning: Gmail service may not be ready"
        tail -5 /tmp/gmail_http.log 2>/dev/null || echo "No log available"
    fi
    sleep 1
done

# ========== 配置 MCP（注册工具到 OpenClaw） ==========
echo "Configuring MCP tools..."
# 注意：当前 openclaw 版本不支持 --command + --args 形式，
# 必须使用 JSON 字符串格式，外层双引号包裹，内部双引号转义。
openclaw mcp set gmail "{\"command\":\"python\",\"args\":[\"$MCP_SERVICE/gmail/server.py\"]}" 2>/dev/null || true

# ========== 部署本地文件到工作区 ==========
echo "Deploying local files to workspace..."
# Per spec: fixture/local_files/ → /opt/local_files/
# The agent expects draft_email.txt at /opt/workspace/draft_email.txt
for src_dir in /opt/local_files /opt/mock_service/local_files /opt/fixture/local_files; do
    if [ -f "$src_dir/draft_email.txt" ]; then
        cp "$src_dir/draft_email.txt" /opt/workspace/draft_email.txt
        echo "✓ draft_email.txt deployed from $src_dir"
        break
    fi
done

# 验证文件已部署
if [ ! -f /opt/workspace/draft_email.txt ]; then
    echo "ERROR: draft_email.txt not found in any expected location!"
    echo "Searching for draft_email.txt..."
    find /opt -name "draft_email.txt" 2>/dev/null || echo "File not found anywhere under /opt"
    ls -la /opt/ /opt/workspace/ /opt/local_files/ 2>/dev/null
else
    echo "✓ Verified: /opt/workspace/draft_email.txt exists ($(wc -c < /opt/workspace/draft_email.txt) bytes)"
fi

echo "=== Initialization complete ==="