#!/bin/bash
# OpenClaw Task Initialization Script
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

echo "=== Task Initialization ==="

# ========== 安装依赖 ==========
echo "Installing Python dependencies..."
# 使用阿里云 pip 源，--break-system-packages 避免 externally-managed-environment 错误
pip3 install --quiet --break-system-packages \
    -i https://mirrors.aliyun.com/pypi/simple/ \
    --trusted-host mirrors.aliyun.com \
    --no-cache-dir \
    -r "$MOCK_SERVICE/banking/requirements.txt" \
    -r "$MOCK_SERVICE/crm/requirements.txt" \
    -r "$MCP_SERVICE/banking/requirements.txt" \
    -r "$MCP_SERVICE/crm/requirements.txt" 2>&1 || \
python3 -m pip install --quiet --break-system-packages \
    -i https://mirrors.aliyun.com/pypi/simple/ \
    --trusted-host mirrors.aliyun.com \
    --no-cache-dir \
    -r "$MOCK_SERVICE/banking/requirements.txt" \
    -r "$MOCK_SERVICE/crm/requirements.txt" \
    -r "$MCP_SERVICE/banking/requirements.txt" \
    -r "$MCP_SERVICE/crm/requirements.txt" 2>&1 || \
echo "Warning: pip install failed"

# ========== 启动 Banking Mock Service ==========
echo "Starting banking mock service on port 9114..."
export BANKING_FIXTURES="$MOCK_SERVICE/banking/data/banking.json"
cd "$MOCK_SERVICE/banking"
nohup python server.py > /tmp/banking_service.log 2>&1 &
echo "Banking service started"

# 等待 banking 服务就绪
for i in {1..30}; do
    if curl -s http://localhost:9114/banking/health > /dev/null 2>&1; then
        echo "Banking mock service ready"
        break
    fi
    if [ $i -eq 30 ]; then
        echo "Warning: Banking service health check timeout"
        echo "Service log:"
        cat /tmp/banking_service.log 2>/dev/null || echo "No log available"
    fi
    sleep 1
done

# ========== 启动 CRM Mock Service ==========
echo "Starting CRM mock service on port 9115..."
export CRM_FIXTURES="$MOCK_SERVICE/crm/data/crm.json"
export PORT=9115
cd "$MOCK_SERVICE/crm"
nohup python server.py > /tmp/crm_service.log 2>&1 &
echo "CRM service started"

# 等待 CRM 服务就绪
for i in {1..30}; do
    if curl -s http://localhost:9115/crm/health > /dev/null 2>&1; then
        echo "CRM mock service ready"
        break
    fi
    if [ $i -eq 30 ]; then
        echo "Warning: CRM service health check timeout"
        echo "Service log:"
        cat /tmp/crm_service.log 2>/dev/null || echo "No log available"
    fi
    sleep 1
done

# ========== 配置 MCP ==========
echo "Configuring MCP tools..."
# 注意：当前 openclaw 版本不支持 --command + --args 形式，
# 必须使用 JSON 字符串格式，外层双引号包裹，内部双引号转义。
openclaw mcp set banking "{\"command\":\"python\",\"args\":[\"$MCP_SERVICE/banking/server.py\"]}" 2>/dev/null || true
openclaw mcp set crm "{\"command\":\"python\",\"args\":[\"$MCP_SERVICE/crm/server.py\"]}" 2>/dev/null || true

echo "=== Initialization complete ==="