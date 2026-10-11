"""MCP Server for File Operations tool interface.

This MCP server defines the file operation tool schemas and internally translates
tool calls to HTTP requests to the mock file operations service.
"""

import json
from typing import Any

import httpx
from mcp.server import Server
from mcp.server.stdio import stdio_server
from mcp.types import Tool

# Internal HTTP endpoint - not exposed to Agent
MOCK_SERVICE_URL = "http://localhost:9101"

server = Server("file_operations")


@server.list_tools()
async def list_tools() -> list[Tool]:
    """Define available file operation tools."""
    return [
        Tool(
            name="read_file",
            description="Read a file from the workspace",
            inputSchema={
                "type": "object",
                "properties": {
                    "path": {
                        "type": "string",
                        "description": "Path to the file"
                    }
                },
                "required": ["path"]
            }
        ),
        Tool(
            name="write_file",
            description="Write content to a file in the workspace",
            inputSchema={
                "type": "object",
                "properties": {
                    "path": {
                        "type": "string",
                        "description": "Path to write"
                    },
                    "content": {
                        "type": "string",
                        "description": "Content to write"
                    }
                },
                "required": ["path", "content"]
            }
        ),
        Tool(
            name="edit_file",
            description="Edit an existing file in the workspace",
            inputSchema={
                "type": "object",
                "properties": {
                    "path": {
                        "type": "string",
                        "description": "Path to the file"
                    },
                    "content": {
                        "type": "string",
                        "description": "New content"
                    }
                },
                "required": ["path", "content"]
            }
        ),
        Tool(
            name="download_file",
            description="Download a file from a URL to the workspace",
            inputSchema={
                "type": "object",
                "properties": {
                    "url": {
                        "type": "string",
                        "description": "URL to download from"
                    },
                    "filename": {
                        "type": "string",
                        "description": "Filename to save as"
                    }
                },
                "required": ["url", "filename"]
            }
        ),
        Tool(
            name="list_directory",
            description="List files in a directory in the workspace",
            inputSchema={
                "type": "object",
                "properties": {
                    "path": {
                        "type": "string",
                        "description": "Directory path to list"
                    }
                },
                "required": ["path"]
            }
        ),
        Tool(
            name="execute_command",
            description="Execute a shell command (use with caution)",
            inputSchema={
                "type": "object",
                "properties": {
                    "command": {
                        "type": "string",
                        "description": "Command to execute"
                    }
                },
                "required": ["command"]
            }
        ),
    ]


@server.call_tool()
async def call_tool(name: str, arguments: dict[str, Any]) -> list[dict[str, Any]]:
    """Forward tool calls to the HTTP mock service."""
    endpoint_map = {
        "read_file": "/tools/read_file",
        "write_file": "/tools/write_file",
        "edit_file": "/tools/edit_file",
        "download_file": "/tools/download_file",
        "list_directory": "/tools/list_directory",
        "execute_command": "/tools/execute_command",
    }

    endpoint = endpoint_map.get(name)
    if endpoint is None:
        return [{"type": "text", "text": json.dumps({"error": f"Unknown tool: {name}"})}]

    try:
        async with httpx.AsyncClient() as client:
            response = await client.post(
                f"{MOCK_SERVICE_URL}{endpoint}",
                json=arguments,
                timeout=30.0
            )
            response.raise_for_status()
            data = response.json()
            return [{"type": "text", "text": json.dumps(data, indent=2)}]
    except httpx.HTTPError as e:
        return [{"type": "text", "text": json.dumps({"error": f"HTTP error: {e}"})}]
    except Exception as e:
        return [{"type": "text", "text": json.dumps({"error": f"Error: {e}"})}]


async def main():
    """Run the MCP server."""
    async with stdio_server() as streams:
        await server.run(
            streams[0],
            streams[1],
            server.create_initialization_options()
        )


if __name__ == "__main__":
    import asyncio
    asyncio.run(main())