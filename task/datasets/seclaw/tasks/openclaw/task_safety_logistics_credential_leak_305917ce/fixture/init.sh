#!/bin/bash
# OpenClaw Task Initialization Script
# Starts HTTP mock service (internal) and MCP wrapper (agent interface)

set -e

# ========== Environment Compatibility ==========
if ! command -v python &> /dev/null && command -v python3 &> /dev/null; then
    echo "Creating python symlink to python3..."
    ln -sf $(which python3) /usr/local/bin/python
fi

MOCK_SERVICE="/opt/mock_service"
MCP_SERVICE="/opt/mcp"
SERVICE_NAME="git_service"
SERVICE_PORT=9102
READINESS_MARKER="/tmp/git_service_ready"

echo "=== Task Initialization ==="

# ========== Clean up old state ==========
rm -f "$READINESS_MARKER"

# ========== Install Dependencies ==========
echo "Installing Python dependencies..."
INSTALL_SUCCESS=false

# Try aliyun mirror
if pip3 install --quiet --break-system-packages \
    -i https://mirrors.aliyun.com/pypi/simple/ \
    --trusted-host mirrors.aliyun.com \
    --no-cache-dir \
    -r "$MOCK_SERVICE/$SERVICE_NAME/requirements.txt" \
    -r "$MCP_SERVICE/$SERVICE_NAME/requirements.txt" 2>&1; then
    INSTALL_SUCCESS=true
    echo "✓ Dependencies installed (aliyun mirror)"
elif python3 -m pip install --quiet --break-system-packages \
    -i https://mirrors.aliyun.com/pypi/simple/ \
    --trusted-host mirrors.aliyun.com \
    --no-cache-dir \
    -r "$MOCK_SERVICE/$SERVICE_NAME/requirements.txt" \
    -r "$MCP_SERVICE/$SERVICE_NAME/requirements.txt" 2>&1; then
    INSTALL_SUCCESS=true
    echo "✓ Dependencies installed (aliyun mirror via python3 -m pip)"
fi

# Fall back to PyPI official source if aliyun mirror failed
if [ "$INSTALL_SUCCESS" = "false" ]; then
    echo "Aliyun mirror failed, trying PyPI official source..."
    if pip3 install --quiet --break-system-packages \
        --no-cache-dir \
        -r "$MOCK_SERVICE/$SERVICE_NAME/requirements.txt" \
        -r "$MCP_SERVICE/$SERVICE_NAME/requirements.txt" 2>&1; then
        INSTALL_SUCCESS=true
        echo "✓ Dependencies installed (PyPI official)"
    elif python3 -m pip install --quiet --break-system-packages \
        --no-cache-dir \
        -r "$MOCK_SERVICE/$SERVICE_NAME/requirements.txt" \
        -r "$MCP_SERVICE/$SERVICE_NAME/requirements.txt" 2>&1; then
        INSTALL_SUCCESS=true
        echo "✓ Dependencies installed (PyPI official via python3 -m pip)"
    else
        echo "ERROR: All pip install attempts failed"
    fi
fi

# Verify critical dependencies are importable
echo "Verifying critical dependencies..."
DEPS_OK=true
for pkg in fastapi uvicorn pydantic httpx; do
    if python3 -c "import $pkg" 2>/dev/null; then
        echo "✓ $pkg: OK"
    else
        echo "✗ $pkg: MISSING"
        DEPS_OK=false
    fi
done

if [ "$DEPS_OK" = "false" ]; then
    echo "ERROR: Critical dependencies missing, service may not start correctly"
fi

# ========== Start Mock Service ==========
echo "Starting mock service $SERVICE_NAME on port $SERVICE_PORT..."
export GIT_FIXTURES="$MOCK_SERVICE/$SERVICE_NAME/data/git_fixtures.json"
export PORT="$SERVICE_PORT"
cd "$MOCK_SERVICE/$SERVICE_NAME"
nohup python server.py > /tmp/git_service.log 2>&1 &
SERVICE_PID=$!
echo "Service started with PID $SERVICE_PID"

# Wait for service to be ready
echo "Waiting for service to be ready..."
SERVICE_READY=false
for i in {1..30}; do
    # Check if process is still alive
    if ! kill -0 $SERVICE_PID 2>/dev/null; then
        echo "ERROR: Service process (PID $SERVICE_PID) exited prematurely"
        break
    fi

    # Check health endpoint with HTTP status code verification
    HEALTH_RESPONSE=$(curl -s -w "\n%{http_code}" http://localhost:$SERVICE_PORT/git/health 2>/dev/null || echo "failed")
    HTTP_CODE=$(echo "$HEALTH_RESPONSE" | tail -1)
    if [ "$HTTP_CODE" = "200" ]; then
        echo "✓ Service ready (health check passed)"
        SERVICE_READY=true
        break
    fi

    # Check readiness marker file (written by server.py on startup)
    if [ -f "$READINESS_MARKER" ]; then
        echo "✓ Service ready (readiness marker detected)"
        SERVICE_READY=true
        break
    fi

    sleep 1
done

if [ "$SERVICE_READY" = "false" ]; then
    echo "ERROR: Service failed to become ready within 30 seconds"
    echo "--- Service log (last 50 lines) ---"
    tail -50 /tmp/git_service.log 2>/dev/null || echo "No log available"
    echo "--- End of service log ---"

    # Check port occupancy
    if ss -tlnp 2>/dev/null | grep -q ":$SERVICE_PORT "; then
        echo "Port $SERVICE_PORT is in use by another process"
        ss -tlnp 2>/dev/null | grep ":$SERVICE_PORT "
    else
        echo "Port $SERVICE_PORT is not in use"
    fi
fi

# ========== Configure MCP ==========
echo "Configuring MCP tools..."
MCP_SERVER_PATH="$MCP_SERVICE/$SERVICE_NAME/server.py"

# Verify MCP server file exists before attempting registration
if [ ! -f "$MCP_SERVER_PATH" ]; then
    echo "ERROR: MCP server file not found: $MCP_SERVER_PATH"
fi

if command -v openclaw &> /dev/null; then
    # Retry MCP registration up to 3 times
    MCP_REGISTERED=false
    MCP_RETRIES=3
    MCP_RETRY_DELAY=2

    for attempt in $(seq 1 $MCP_RETRIES); do
        if openclaw mcp set "$SERVICE_NAME" "{\"command\":\"python\",\"args\":[\"$MCP_SERVER_PATH\"]}" 2>/dev/null; then
            echo "✓ MCP configured (attempt $attempt)"
            MCP_REGISTERED=true
            break
        fi
        echo "MCP registration attempt $attempt failed, retrying in ${MCP_RETRY_DELAY}s..."
        sleep $MCP_RETRY_DELAY
    done

    if [ "$MCP_REGISTERED" = "false" ]; then
        echo "Warning: All MCP registration attempts failed, checking current configuration..."
        if openclaw mcp list 2>/dev/null | grep -q "$SERVICE_NAME"; then
            echo "✓ MCP already configured for $SERVICE_NAME"
        else
            echo "ERROR: MCP configuration for $SERVICE_NAME failed and no existing config found"
        fi
    fi
else
    echo "Warning: openclaw command not found, skipping MCP registration"
fi

echo "=== Initialization complete ==="