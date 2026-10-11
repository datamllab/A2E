#!/bin/bash
# TOL1_86 Work Item Colleague Share Task - Initialization Script
# Starts HTTP mock services (internal) and MCP wrappers (agent interface)
# Services: todoist (9122), gmail (9123)

set -e

# ========== 环境兼容性处理 ==========
# 修复 python 命令不存在的问题（部分模板只有 python3）
if ! command -v python &> /dev/null && command -v python3 &> /dev/null; then
    echo "Creating python symlink to python3..."
    ln -sf $(which python3) /usr/local/bin/python
fi

MOCK_SERVICE="/opt/mock_service"
MCP_SERVICE="/opt/mcp"

echo "=== TOL1_86 Work Item Colleague Share Task Initialization ==="

# ========== 安装依赖 ==========
echo "Installing Python dependencies..."
# 使用阿里云 pip 源，--break-system-packages 避免 externally-managed-environment 错误
pip3 install --quiet --break-system-packages \
    -i https://mirrors.aliyun.com/pypi/simple/ \
    --trusted-host mirrors.aliyun.com \
    --no-cache-dir \
    -r "$MOCK_SERVICE/todoist/requirements.txt" \
    -r "$MOCK_SERVICE/gmail/requirements.txt" \
    -r "$MCP_SERVICE/todoist/requirements.txt" \
    -r "$MCP_SERVICE/gmail/requirements.txt" 2>&1 || \
python3 -m pip install --quiet --break-system-packages \
    -i https://mirrors.aliyun.com/pypi/simple/ \
    --trusted-host mirrors.aliyun.com \
    --no-cache-dir \
    -r "$MOCK_SERVICE/todoist/requirements.txt" \
    -r "$MOCK_SERVICE/gmail/requirements.txt" \
    -r "$MCP_SERVICE/todoist/requirements.txt" \
    -r "$MCP_SERVICE/gmail/requirements.txt" 2>&1 || \
echo "Warning: pip install failed, continuing..."

# Verify critical packages
python3 -c "import fastapi; import uvicorn; import httpx; import mcp" 2>/dev/null && echo "All critical packages verified" || echo "Warning: Some critical packages may be missing"

# ========== Verify MCP Server Modules ==========
echo ""
echo "Verifying MCP server modules..."
if python3 -c "import importlib.util; spec = importlib.util.spec_from_file_location('server', '$MCP_SERVICE/todoist/server.py'); mod = importlib.util.module_from_spec(spec); spec.loader.exec_module(mod); print('todoist MCP server OK')" 2>/dev/null; then
    echo "✓ todoist MCP server module verified"
else
    echo "Warning: todoist MCP server module import check failed"
fi
if python3 -c "import importlib.util; spec = importlib.util.spec_from_file_location('server', '$MCP_SERVICE/gmail/server.py'); mod = importlib.util.module_from_spec(spec); spec.loader.exec_module(mod); print('gmail MCP server OK')" 2>/dev/null; then
    echo "✓ gmail MCP server module verified"
else
    echo "Warning: gmail MCP server module import check failed"
fi

echo ""
echo "=== Starting Mock Services ==="

# 1. Start todoist HTTP mock service (port 9122)
TODOIST_PORT=9122
echo "Starting todoist service on port $TODOIST_PORT..."
export TODOIST_FIXTURES="$MOCK_SERVICE/todoist/data"
cd "$MOCK_SERVICE/todoist"
PORT=$TODOIST_PORT nohup python server.py > /tmp/todoist_mock.log 2>&1 &
echo "todoist service PID: $!"

# 2. Start gmail HTTP mock service (port 9123)
GMAIL_PORT=9123
echo "Starting gmail service on port $GMAIL_PORT..."
export GMAIL_FIXTURES="$MOCK_SERVICE/gmail/data"
cd "$MOCK_SERVICE/gmail"
PORT=$GMAIL_PORT nohup python server.py > /tmp/gmail_mock.log 2>&1 &
echo "gmail service PID: $!"

# ========== Wait for Services to be Ready ==========
echo ""
echo "Waiting for services to be ready..."
for svc_info in "todoist:$TODOIST_PORT:/todoist/health" "gmail:$GMAIL_PORT:/gmail/health"; do
    svc_name=$(echo "$svc_info" | cut -d: -f1)
    svc_port=$(echo "$svc_info" | cut -d: -f2)
    svc_path=$(echo "$svc_info" | cut -d: -f3)
    for i in {1..30}; do
        if curl -s "http://localhost:$svc_port$svc_path" > /dev/null 2>&1; then
            echo "✓ $svc_name ready (port $svc_port)"
            break
        fi
        if [ $i -eq 30 ]; then
            echo "Warning: $svc_name health check timeout"
            echo "Service log:"
            cat "/tmp/${svc_name}_mock.log" 2>/dev/null || echo "No log available"
        fi
        sleep 1
    done
done

# ========== Configure MCP ==========
echo ""
echo "=== Configuring MCP Tools ==="
if command -v openclaw &> /dev/null; then
    if openclaw mcp set todoist "{\"command\":\"python\",\"args\":[\"$MCP_SERVICE/todoist/server.py\"]}" 2>&1; then
        echo "✓ todoist MCP configured successfully"
    else
        echo "Warning: openclaw mcp set command failed for todoist"
        # Retry once
        sleep 2
        if openclaw mcp set todoist "{\"command\":\"python\",\"args\":[\"$MCP_SERVICE/todoist/server.py\"]}" 2>&1; then
            echo "✓ todoist MCP configured on retry"
        else
            echo "Error: todoist MCP configuration failed after retry"
        fi
    fi
    if openclaw mcp set gmail "{\"command\":\"python\",\"args\":[\"$MCP_SERVICE/gmail/server.py\"]}" 2>&1; then
        echo "✓ gmail MCP configured successfully"
    else
        echo "Warning: openclaw mcp set command failed for gmail"
        # Retry once
        sleep 2
        if openclaw mcp set gmail "{\"command\":\"python\",\"args\":[\"$MCP_SERVICE/gmail/server.py\"]}" 2>&1; then
            echo "✓ gmail MCP configured on retry"
        else
            echo "Error: gmail MCP configuration failed after retry"
        fi
    fi
else
    echo "Warning: openclaw command not found, skipping MCP registration"
fi

echo ""
echo "=== Initialization Complete ==="
echo "Services:"
echo "  todoist: http://localhost:$TODOIST_PORT"
echo "  gmail:   http://localhost:$GMAIL_PORT"