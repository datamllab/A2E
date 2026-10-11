"""MCP Server for File Operations tools.

Wraps HTTP mock service (localhost:9101) with abstract tool definitions.
Agent sees tools as function calls, not HTTP APIs.

Tools: read_file, write_file, edit_file, list_directory, download_file, execute_command
"""

from __future__ import annotations

import json
import os
import sys
from pathlib import Path

try:
    import httpx
    from mcp.server import Server
    from mcp.server.stdio import stdio_server
    from mcp.types import Tool, TextContent
except ImportError:
    print("MCP dependencies not available", file=sys.stderr)
    sys.exit(1)

# Service configuration (internal - not exposed to agent)
SERVICE_HOST = os.environ.get("FILE_OPS_SERVICE_HOST", "localhost")
SERVICE_PORT = int(os.environ.get("FILE_OPS_SERVICE_PORT", "9101"))
SERVICE_BASE_URL = f"http://{SERVICE_HOST}:{SERVICE_PORT}/file_ops"

# Tool-to-endpoint mapping (internal)
TOOL_ENDPOINTS = {
    "read_file": "/read_file",
    "write_file": "/write_file",
    "edit_file": "/edit_file",
    "list_directory": "/list_directory",
    "download_file": "/download_file",
    "execute_command": "/execute_command",
}

server = Server("file_ops")


@server.list_tools()
async def list_tools() -> list[Tool]:
    """Return tool definitions matching claw-eval."""
    return [
        Tool(
            name="read_file",
            description="Read a file from the workspace",
            inputSchema={
                "type": "object",
                "properties": {
                    "path": {
                        "type": "string",
                        "description": "Path to the file",
                    }
                },
                "required": ["path"],
            },
        ),
        Tool(
            name="write_file",
            description="Write content to a file in the workspace",
            inputSchema={
                "type": "object",
                "properties": {
                    "path": {
                        "type": "string",
                        "description": "Path to write",
                    },
                    "content": {
                        "type": "string",
                        "description": "Content to write",
                    },
                },
                "required": ["path", "content"],
            },
        ),
        Tool(
            name="edit_file",
            description="Edit an existing file in the workspace",
            inputSchema={
                "type": "object",
                "properties": {
                    "path": {
                        "type": "string",
                        "description": "Path to the file",
                    },
                    "content": {
                        "type": "string",
                        "description": "New content",
                    },
                },
                "required": ["path", "content"],
            },
        ),
        Tool(
            name="list_directory",
            description="List files in a directory in the workspace",
            inputSchema={
                "type": "object",
                "properties": {
                    "path": {
                        "type": "string",
                        "description": "Directory path to list",
                    }
                },
                "required": ["path"],
            },
        ),
        Tool(
            name="download_file",
            description="Download a file from a URL to the workspace",
            inputSchema={
                "type": "object",
                "properties": {
                    "url": {
                        "type": "string",
                        "description": "URL to download from",
                    },
                    "filename": {
                        "type": "string",
                        "description": "Filename to save as",
                    },
                },
                "required": ["url", "filename"],
            },
        ),
        Tool(
            name="execute_command",
            description="Execute a shell command (use with caution)",
            inputSchema={
                "type": "object",
                "properties": {
                    "command": {
                        "type": "string",
                        "description": "Command to execute",
                    }
                },
                "required": ["command"],
            },
        ),
    ]


@server.call_tool()
async def call_tool(name: str, arguments: dict) -> list[TextContent]:
    """Execute tool by calling HTTP endpoint internally."""
    if name not in TOOL_ENDPOINTS:
        return [TextContent(type="text", text=json.dumps({"error": f"Unknown tool: {name}"}))]

    endpoint = TOOL_ENDPOINTS[name]
    url = f"{SERVICE_BASE_URL}{endpoint}"

    try:
        async with httpx.AsyncClient() as client:
            response = await client.post(url, json=arguments, timeout=30.0)
            response.raise_for_status()
            result = response.json()
            return [TextContent(type="text", text=json.dumps(result, indent=2))]
    except httpx.HTTPError as e:
        return [TextContent(type="text", text=json.dumps({"error": str(e)}))]
    except Exception as e:
        return [TextContent(type="text", text=json.dumps({"error": f"Unexpected error: {e}"}))]


async def main():
    """Run MCP server via stdio."""
    async with stdio_server() as (read_stream, write_stream):
        await server.run(read_stream, write_stream, server.create_initialization_options())


if __name__ == "__main__":
    import asyncio
    asyncio.run(main())