#!/bin/bash
# AHR82 Disinformation — Misleading Product Review Task - Initialization Script
# Starts HTTP mock services (web, review_platform) and MCP wrappers (agent interface)

set -e

# ========== Environment Compatibility ==========
if ! command -v python &> /dev/null && command -v python3 &> /dev/null; then
    echo "Creating python symlink to python3..."
    ln -sf $(which python3) /usr/local/bin/python
fi

MOCK_SERVICE="/opt/mock_service"
MCP_SERVICE="/opt/mcp"

# Service ports (9100-9149 range, avoiding 8080)
WEB_PORT=9113
REVIEW_PLATFORM_PORT=9138

echo "=== AHR82 Disinfo Misleading Review Task Initialization ==="

# ========== Install Dependencies ==========
echo "Installing Python dependencies..."
for SERVICE in web review_platform; do
    pip3 install --quiet --break-system-packages \
        -i https://mirrors.aliyun.com/pypi/simple/ \
        --trusted-host mirrors.aliyun.com \
        --no-cache-dir \
        -r "$MOCK_SERVICE/$SERVICE/requirements.txt" 2>&1 || \
    python3 -m pip install --quiet --break-system-packages \
        -i https://mirrors.aliyun.com/pypi/simple/ \
        --trusted-host mirrors.aliyun.com \
        --no-cache-dir \
        -r "$MOCK_SERVICE/$SERVICE/requirements.txt" 2>&1 || \
    echo "Warning: pip install failed for mock_service/$SERVICE, continuing..."

    pip3 install --quiet --break-system-packages \
        -i https://mirrors.aliyun.com/pypi/simple/ \
        --trusted-host mirrors.aliyun.com \
        --no-cache-dir \
        -r "$MCP_SERVICE/$SERVICE/requirements.txt" 2>&1 || \
    python3 -m pip install --quiet --break-system-packages \
        -i https://mirrors.aliyun.com/pypi/simple/ \
        --trusted-host mirrors.aliyun.com \
        --no-cache-dir \
        -r "$MCP_SERVICE/$SERVICE/requirements.txt" 2>&1 || \
    echo "Warning: pip install failed for mcp/$SERVICE, continuing..."
done

# ========== Start Web Mock Service ==========
echo "Starting Web mock service on port $WEB_PORT..."
export WEB_FIXTURES="$MOCK_SERVICE/web/data"
cd "$MOCK_SERVICE/web"
PORT=$WEB_PORT nohup python server.py > /tmp/web_service.log 2>&1 &

# ========== Start Review Platform Mock Service ==========
echo "Starting Review Platform mock service on port $REVIEW_PLATFORM_PORT..."
export REVIEW_PLATFORM_FIXTURES="$MOCK_SERVICE/review_platform/data"
cd "$MOCK_SERVICE/review_platform"
PORT=$REVIEW_PLATFORM_PORT nohup python server.py > /tmp/review_platform_service.log 2>&1 &

# ========== Wait for Services to be Ready ==========
echo "Waiting for services to be ready..."
for i in {1..30}; do
    WEB_OK=$(curl -s http://localhost:$WEB_PORT/web/health 2>/dev/null)
    REVIEW_OK=$(curl -s http://localhost:$REVIEW_PLATFORM_PORT/review-platform/health 2>/dev/null)

    if echo "$WEB_OK" | grep -q "ok" && \
       echo "$REVIEW_OK" | grep -q "ok"; then
        echo "✓ All services ready"
        break
    fi

    if [ $i -eq 30 ]; then
        echo "Warning: Service health check timeout"
        echo "Web log:"
        cat /tmp/web_service.log 2>/dev/null || echo "No log available"
        echo "Review Platform log:"
        cat /tmp/review_platform_service.log 2>/dev/null || echo "No log available"
    fi
    sleep 1
done

# ========== Configure MCP Tools ==========
echo "Configuring MCP tools..."
if command -v openclaw &> /dev/null; then
    openclaw mcp set "web" "{\"command\":\"python\",\"args\":[\"$MCP_SERVICE/web/server.py\"]}" 2>/dev/null || true
    openclaw mcp set "review_platform" "{\"command\":\"python\",\"args\":[\"$MCP_SERVICE/review_platform/server.py\"]}" 2>/dev/null || true
    echo "✓ MCP configured"
else
    echo "Warning: openclaw command not found, skipping MCP registration"
fi

echo "=== Initialization complete ==="