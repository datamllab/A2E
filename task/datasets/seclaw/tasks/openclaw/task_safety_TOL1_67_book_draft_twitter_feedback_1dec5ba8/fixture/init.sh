#!/bin/bash
# OpenClaw Task Initialization Script
# Starts HTTP mock services (internal) and MCP wrappers (agent interface)
# Services: file_storage (9133), social_media (9130)

set -e

# ========== Environment Compatibility ==========
# Fix python command if not exists (some templates only have python3)
if ! command -v python &> /dev/null && command -v python3 &> /dev/null; then
    echo "Creating python symlink to python3..."
    ln -sf $(which python3) /usr/local/bin/python
fi

MOCK_SERVICE="/opt/mock_service"
MCP_SERVICE="/opt/mcp"

echo "=== Task Initialization ==="

# ========== Install Dependencies ==========
echo "Installing Python dependencies..."
INSTALL_SUCCESS=false

# Try aliyun mirror
if pip3 install --quiet --break-system-packages \
    -i https://mirrors.aliyun.com/pypi/simple/ \
    --trusted-host mirrors.aliyun.com \
    --no-cache-dir \
    -r "$MOCK_SERVICE/file_storage/requirements.txt" \
    -r "$MOCK_SERVICE/social_media/requirements.txt" \
    -r "$MCP_SERVICE/file_storage/requirements.txt" \
    -r "$MCP_SERVICE/social_media/requirements.txt" 2>&1; then
    INSTALL_SUCCESS=true
    echo "✓ Dependencies installed (aliyun mirror)"
elif python3 -m pip install --quiet --break-system-packages \
    -i https://mirrors.aliyun.com/pypi/simple/ \
    --trusted-host mirrors.aliyun.com \
    --no-cache-dir \
    -r "$MOCK_SERVICE/file_storage/requirements.txt" \
    -r "$MOCK_SERVICE/social_media/requirements.txt" \
    -r "$MCP_SERVICE/file_storage/requirements.txt" \
    -r "$MCP_SERVICE/social_media/requirements.txt" 2>&1; then
    INSTALL_SUCCESS=true
    echo "✓ Dependencies installed (aliyun mirror via python3 -m pip)"
fi

# Fall back to PyPI official source if aliyun mirror failed
if [ "$INSTALL_SUCCESS" = "false" ]; then
    echo "Aliyun mirror failed, trying PyPI official source..."
    if pip3 install --quiet --break-system-packages \
        --no-cache-dir \
        -r "$MOCK_SERVICE/file_storage/requirements.txt" \
        -r "$MOCK_SERVICE/social_media/requirements.txt" \
        -r "$MCP_SERVICE/file_storage/requirements.txt" \
        -r "$MCP_SERVICE/social_media/requirements.txt" 2>&1; then
        INSTALL_SUCCESS=true
        echo "✓ Dependencies installed (PyPI official)"
    elif python3 -m pip install --quiet --break-system-packages \
        --no-cache-dir \
        -r "$MOCK_SERVICE/file_storage/requirements.txt" \
        -r "$MOCK_SERVICE/social_media/requirements.txt" \
        -r "$MCP_SERVICE/file_storage/requirements.txt" \
        -r "$MCP_SERVICE/social_media/requirements.txt" 2>&1; then
        INSTALL_SUCCESS=true
        echo "✓ Dependencies installed (PyPI official via python3 -m pip)"
    else
        echo "Warning: pip install failed, continuing..."
    fi
fi

# Verify critical packages
python3 -c "import fastapi; import uvicorn; import httpx; import mcp" 2>/dev/null && echo "All critical packages verified" || echo "Warning: Some critical packages may be missing"

echo ""
echo "=== Starting Mock Services ==="

# 1. Start file_storage HTTP mock service (port 9133)
FILE_STORAGE_PORT=9133
echo "Starting file_storage service on port $FILE_STORAGE_PORT..."
export FILE_STORAGE_FIXTURES="$MOCK_SERVICE/file_storage/data/file_storage.json"
cd "$MOCK_SERVICE/file_storage"
PORT=$FILE_STORAGE_PORT nohup python server.py > /tmp/file_storage_mock.log 2>&1 &
echo "file_storage service PID: $!"

# 2. Start social_media HTTP mock service (port 9130)
SOCIAL_MEDIA_PORT=9130
echo "Starting social_media service on port $SOCIAL_MEDIA_PORT..."
export SOCIAL_MEDIA_FIXTURES="$MOCK_SERVICE/social_media/data/social_media.json"
cd "$MOCK_SERVICE/social_media"
PORT=$SOCIAL_MEDIA_PORT nohup python server.py > /tmp/social_media_mock.log 2>&1 &
echo "social_media service PID: $!"

# ========== Wait for Services to be Ready ==========
echo ""
echo "Waiting for services to be ready..."
for svc_info in "file_storage:$FILE_STORAGE_PORT:/file_storage/health" "social_media:$SOCIAL_MEDIA_PORT:/social_media/health"; do
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
    # Retry MCP registration up to 3 times for each service
    for svc_name in "file_storage" "social_media"; do
        MCP_REGISTERED=false
        MCP_RETRIES=3
        MCP_RETRY_DELAY=2
        MCP_SERVER_PATH="$MCP_SERVICE/$svc_name/server.py"

        if [ ! -f "$MCP_SERVER_PATH" ]; then
            echo "Warning: MCP server file not found: $MCP_SERVER_PATH"
            continue
        fi

        for attempt in $(seq 1 $MCP_RETRIES); do
            if openclaw mcp set "$svc_name" "{\"command\":\"python\",\"args\":[\"$MCP_SERVER_PATH\"]}" 2>/dev/null; then
                echo "✓ $svc_name MCP configured (attempt $attempt)"
                MCP_REGISTERED=true
                break
            fi
            echo "$svc_name MCP registration attempt $attempt failed, retrying in ${MCP_RETRY_DELAY}s..."
            sleep $MCP_RETRY_DELAY
        done

        if [ "$MCP_REGISTERED" = "false" ]; then
            echo "Warning: $svc_name MCP registration failed, checking current configuration..."
            if openclaw mcp list 2>/dev/null | grep -q "$svc_name"; then
                echo "✓ $svc_name MCP already configured"
            else
                echo "Warning: $svc_name MCP configuration failed"
            fi
        fi
    done
else
    echo "Warning: openclaw command not found, skipping MCP registration"
fi

echo ""
echo "=== Initialization Complete ==="
echo "Services:"
echo "  file_storage: http://localhost:$FILE_STORAGE_PORT"
echo "  social_media: http://localhost:$SOCIAL_MEDIA_PORT"