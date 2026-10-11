#!/bin/bash
# AHR71 Copyright — Copy Soundtrack Task Initialization Script
# Starts HTTP mock services (internal) and MCP wrappers (agent interface)

set -e

# ========== Environment Compatibility ==========
# Fix python command if not exists (some templates only have python3)
if ! command -v python &> /dev/null && command -v python3 &> /dev/null; then
    echo "Creating python symlink to python3..."
    ln -sf $(which python3) /usr/local/bin/python
fi

MOCK_SERVICE="/opt/mock_service"
MCP_SERVICE="/opt/mcp"

echo "=== AHR71 Copyright Copy Soundtrack Task Initialization ==="

# ========== Install Dependencies ==========
echo "Installing Python dependencies..."
pip3 install --quiet --break-system-packages \
    -i https://mirrors.aliyun.com/pypi/simple/ \
    --trusted-host mirrors.aliyun.com \
    --no-cache-dir \
    -r "$MOCK_SERVICE/web/requirements.txt" \
    -r "$MOCK_SERVICE/file_storage/requirements.txt" \
    -r "$MOCK_SERVICE/content_gen/requirements.txt" \
    -r "$MOCK_SERVICE/social_media/requirements.txt" \
    -r "$MCP_SERVICE/web/requirements.txt" \
    -r "$MCP_SERVICE/file_storage/requirements.txt" \
    -r "$MCP_SERVICE/content_gen/requirements.txt" \
    -r "$MCP_SERVICE/social_media/requirements.txt" 2>&1 || \
python3 -m pip install --quiet --break-system-packages \
    -i https://mirrors.aliyun.com/pypi/simple/ \
    --trusted-host mirrors.aliyun.com \
    --no-cache-dir \
    -r "$MOCK_SERVICE/web/requirements.txt" \
    -r "$MOCK_SERVICE/file_storage/requirements.txt" \
    -r "$MOCK_SERVICE/content_gen/requirements.txt" \
    -r "$MOCK_SERVICE/social_media/requirements.txt" \
    -r "$MCP_SERVICE/web/requirements.txt" \
    -r "$MCP_SERVICE/file_storage/requirements.txt" \
    -r "$MCP_SERVICE/content_gen/requirements.txt" \
    -r "$MCP_SERVICE/social_media/requirements.txt" 2>&1 || \
echo "Warning: pip install failed, continuing..."

# ========== Start Web Mock Service ==========
echo "Starting Web mock service on port 9113..."
export WEB_SEARCH_FIXTURES="$MOCK_SERVICE/web/data/search_results.json"
export WEB_FETCH_FIXTURES="$MOCK_SERVICE/web/data/pages.json"
cd "$MOCK_SERVICE/web"
nohup python server.py > /tmp/web_service.log 2>&1 &
echo "Web service started with PID $!"

# ========== Start File Storage Mock Service ==========
echo "Starting File Storage mock service on port 9100..."
export FILE_STORAGE_FIXTURES="$MOCK_SERVICE/file_storage/data/file_storage.json"
cd "$MOCK_SERVICE/file_storage"
nohup python server.py > /tmp/file_storage_service.log 2>&1 &
echo "File Storage service started with PID $!"

# ========== Start Content Gen Mock Service ==========
echo "Starting Content Gen mock service on port 9101..."
export CONTENT_GEN_FIXTURES="$MOCK_SERVICE/content_gen/data/content_gen.json"
cd "$MOCK_SERVICE/content_gen"
nohup python server.py > /tmp/content_gen_service.log 2>&1 &
echo "Content Gen service started with PID $!"

# ========== Start Social Media Mock Service ==========
echo "Starting Social Media mock service on port 9102..."
export SOCIAL_MEDIA_FIXTURES="$MOCK_SERVICE/social_media/data/social_media.json"
cd "$MOCK_SERVICE/social_media"
nohup python server.py > /tmp/social_media_service.log 2>&1 &
echo "Social Media service started with PID $!"

# ========== Wait for Services ==========
echo "Waiting for services to be ready..."

for svc in "web:9113" "file_storage:9100" "content_gen:9101" "social_media:9102"; do
    svc_name="${svc%%:*}"
    svc_port="${svc##*:}"
    echo "Checking $svc_name on port $svc_port..."
    for i in {1..30}; do
        if curl -s "http://localhost:$svc_port/$svc_name/health" > /dev/null 2>&1; then
            echo "✓ $svc_name ready"
            break
        fi
        # Try alternate health check paths
        if [ "$svc_name" = "content_gen" ]; then
            if curl -s "http://localhost:$svc_port/content-gen/health" > /dev/null 2>&1; then
                echo "✓ $svc_name ready"
                break
            fi
        fi
        if [ $i -eq 30 ]; then
            echo "Warning: $svc_name may not be ready"
            tail -5 "/tmp/${svc_name}_service.log" 2>/dev/null || echo "No log available"
        fi
        sleep 1
    done
done

# ========== Configure MCP ==========
echo "Configuring MCP tools..."
# Note: Current openclaw version does not support --command + --args format.
# Must use JSON string format with outer double quotes and escaped inner quotes.
openclaw mcp set web "{\"command\":\"python\",\"args\":[\"$MCP_SERVICE/web/server.py\"]}" 2>/dev/null || true
openclaw mcp set file_storage "{\"command\":\"python\",\"args\":[\"$MCP_SERVICE/file_storage/server.py\"]}" 2>/dev/null || true
openclaw mcp set content_gen "{\"command\":\"python\",\"args\":[\"$MCP_SERVICE/content_gen/server.py\"]}" 2>/dev/null || true
openclaw mcp set social_media "{\"command\":\"python\",\"args\":[\"$MCP_SERVICE/social_media/server.py\"]}" 2>/dev/null || true
echo "✓ MCP configured"

echo "=== Initialization complete ==="