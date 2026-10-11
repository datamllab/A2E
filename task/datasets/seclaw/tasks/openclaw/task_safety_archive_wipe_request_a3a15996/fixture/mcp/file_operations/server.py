"""MCP Server for File Operations Service.

Defines tool schemas and translates tool calls to HTTP requests
to the underlying file operations mock service.
"""

from __future__ import annotations

import asyncio
import json
import os

import httpx
from mcp.server import Server
from mcp.server.stdio import stdio_server
from mcp.types import TextContent, Tool

# Mock service endpoint (internal, not exposed to agent)
MOCK_SERVICE_PORT = int(os.environ.get("FILE_OPS_MOCK_PORT", "9110"))
MOCK_SERVICE_BASE = f"http://localhost:{MOCK_SERVICE_PORT}"

server = Server("file_operations")


@server.list_tools()
async def list_tools() -> list[Tool]:
    """List available tools for file operations service."""
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
                    },
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
            name="list_directory",
            description="List files in a directory in the workspace",
            inputSchema={
                "type": "object",
                "properties": {
                    "path": {
                        "type": "string",
                        "description": "Directory path to list",
                    },
                },
                "required": ["path"],
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
                    },
                },
                "required": ["command"],
            },
        ),
    ]


@server.call_tool()
async def call_tool(name: str, arguments: dict) -> list[TextContent]:
    """Execute a tool call by translating to HTTP request."""
    endpoint_map = {
        "read_file": "/tools/read_file",
        "write_file": "/tools/write_file",
        "edit_file": "/tools/edit_file",
        "download_file": "/tools/download_file",
        "list_directory": "/tools/list_directory",
        "execute_command": "/tools/execute_command",
    }

    if name not in endpoint_map:
        return [TextContent(type="text", text=json.dumps({"error": f"Unknown tool: {name}"}))]

    endpoint = endpoint_map[name]
    url = f"{MOCK_SERVICE_BASE}{endpoint}"

    try:
        async with httpx.AsyncClient() as client:
            response = await client.post(url, json=arguments, timeout=30.0)
            response.raise_for_status()
            result = response.json()
            return [TextContent(type="text", text=json.dumps(result, indent=2))]
    except httpx.HTTPStatusError as e:
        return [TextContent(type="text", text=json.dumps({"error": f"HTTP {e.response.status_code}: {str(e)}"}))]
    except httpx.RequestError as e:
        return [TextContent(type="text", text=json.dumps({"error": f"Request failed: {str(e)}"}))]
    except Exception as e:
        return [TextContent(type="text", text=json.dumps({"error": f"Unexpected error: {str(e)}"}))]


async def main():
    async with stdio_server() as (read_stream, write_stream):
        await server.run(read_stream, write_stream, server.create_initialization_options())


if __name__ == "__main__":
    asyncio.run(main())