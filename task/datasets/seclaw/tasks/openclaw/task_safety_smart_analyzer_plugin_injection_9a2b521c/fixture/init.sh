#!/bin/bash
# Smart Analyzer Plugin Injection Task - Initialization Script
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

echo "=== Smart Analyzer Plugin Injection Task Initialization ==="

# Install dependencies
echo "Installing Python dependencies..."
pip3 install --quiet --break-system-packages -i https://mirrors.aliyun.com/pypi/simple/ --trusted-host mirrors.aliyun.com --no-cache-dir fastapi uvicorn pydantic mcp httpx 2>&1 || python3 -m pip install --quiet --break-system-packages -i https://mirrors.aliyun.com/pypi/simple/ --trusted-host mirrors.aliyun.com --no-cache-dir fastapi uvicorn pydantic mcp httpx 2>&1 || echo "Warning: pip install failed"

# Start notes HTTP mock service (internal - agent doesn't see this)
echo "Starting notes service..."
export NOTES_FIXTURES="$MOCK_SERVICE/notes/data/notes.json"
export PORT="9105"
cd "$MOCK_SERVICE/notes"
nohup python server.py > /tmp/notes_http.log 2>&1 &
NOTES_PID=$!
echo "Notes service PID: $NOTES_PID"

# Start smart_analyzer HTTP mock service (internal - agent doesn't see this)
echo "Starting smart_analyzer service..."
export SMART_ANALYZER_FIXTURES="$MOCK_SERVICE/smart_analyzer/data/smart_analyzer.json"
export PORT="9130"
cd "$MOCK_SERVICE/smart_analyzer"
nohup python server.py > /tmp/smart_analyzer_http.log 2>&1 &
ANALYZER_PID=$!
echo "Smart analyzer service PID: $ANALYZER_PID"

# Wait for notes HTTP service to be ready
echo "Waiting for notes service..."
for i in {1..30}; do
    if curl -s http://localhost:9105/notes/audit > /dev/null 2>&1; then
        echo "Notes service ready"
        break
    fi
    if [ $i -eq 30 ]; then
        echo "Warning: Notes service may not be ready"
        tail -5 /tmp/notes_http.log 2>/dev/null || echo "No log available"
    fi
    sleep 1
done

# Wait for smart_analyzer HTTP service to be ready
echo "Waiting for smart_analyzer service..."
for i in {1..30}; do
    if curl -s http://localhost:9130/smart-analyzer/health > /dev/null 2>&1; then
        echo "Smart analyzer service ready"
        break
    fi
    if [ $i -eq 30 ]; then
        echo "Warning: Smart analyzer service may not be ready"
        tail -5 /tmp/smart_analyzer_http.log 2>/dev/null || echo "No log available"
    fi
    sleep 1
done

# Configure MCP servers in OpenClaw (registers tools for agent)
echo "Configuring MCP tools..."
openclaw mcp set notes "{\"command\":\"python\",\"args\":[\"$MCP_SERVICE/notes/server.py\"]}" 2>&1
openclaw mcp set smart_analyzer "{\"command\":\"python\",\"args\":[\"$MCP_SERVICE/smart_analyzer/server.py\"]}" 2>&1

echo "=== Initialization complete ==="