"""HTTP Mock Service for code_editor.

Provides /code_editor/read_file and /code_editor/write_file endpoints.
Logs all operations for audit by the grader.
"""

from fastapi import FastAPI
from fastapi.responses import JSONResponse
import json
import os

app = FastAPI()

FIXTURES_PATH = os.environ.get(
    "CODE_EDITOR_FIXTURES", "/opt/mock_service/code_editor/data"
)

# Audit log for grader inspection
audit_log: list[dict] = []

# Loaded fixture files
files: dict[str, str] = {}

# Predefined tool responses
tool_responses: dict[str, dict] = {}


def load_fixtures():
    """Load fixture data from JSON file."""
    global files, tool_responses
    data_file = os.path.join(FIXTURES_PATH, "service_data.json")
    try:
        with open(data_file) as f:
            data = json.load(f)
            files = data.get("files", {})
            tool_responses = data.get("tool_responses", {})
    except Exception as e:
        print(f"Warning: Failed to load fixtures from {data_file}: {e}")


@app.on_event("startup")
async def startup():
    load_fixtures()


@app.post("/code_editor/read_file")
async def read_file(request: dict):
    """Read file content from fixture data."""
    audit_log.append(
        {"endpoint": "/code_editor/read_file", "request_body": request}
    )

    file_path = request.get("file_path", "")

    # Try to match the file name within the path
    for key, content in files.items():
        if key in file_path or file_path.endswith(key):
            return {"content": content, "status": "ok"}

    # Fallback: return error if file not found
    return {"content": f"File not found: {file_path}", "status": "error"}


@app.post("/code_editor/write_file")
async def write_file(request: dict):
    """Log write operations and return success."""
    audit_log.append(
        {"endpoint": "/code_editor/write_file", "request_body": request}
    )

    # Check if there's a predefined response
    if "write_file" in tool_responses:
        return tool_responses["write_file"]

    return {"status": "ok", "message": "File written successfully"}


@app.get("/code_editor/audit")
async def audit():
    """Return audit log for grader inspection."""
    return {"calls": audit_log}


@app.get("/code_editor/health")
async def health():
    """Health check endpoint."""
    return {"status": "ok"}


@app.post("/code_editor/reset")
async def reset():
    """Reset audit log and reload fixtures."""
    global audit_log
    audit_log = []
    load_fixtures()
    return {"status": "ok"}


if __name__ == "__main__":
    import uvicorn

    uvicorn.run(app, host="0.0.0.0", port=9101)
