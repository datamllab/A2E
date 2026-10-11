"""MCP Server for file operations tools.

Defines tool schemas and translates tool calls to HTTP requests
to the mock file operations service running on port 9110.
"""

from __future__ import annotations

import asyncio
import json
from typing import Any

import httpx
from mcp.server import Server
from mcp.server.stdio import stdio_server
from mcp.types import Tool, TextContent

# HTTP endpoint for the mock file operations service (internal, not exposed to Agent)
FILE_OPS_SERVICE_URL = "http://localhost:9110"

server = Server("file_ops")


@server.list_tools()
async def list_tools() -> list[Tool]:
    """Define available file operation tools."""
    return [
        Tool(
            name="read_file",
            description="Read a file from the workspace.",
            inputSchema={
                "type": "object",
                "properties": {
                    "path": {
                        "type": "string",
                        "description": "Path to the file to read."
                    }
                },
                "required": ["path"]
            }
        ),
        Tool(
            name="write_file",
            description="Write content to a file in the workspace.",
            inputSchema={
                "type": "object",
                "properties": {
                    "path": {
                        "type": "string",
                        "description": "Path to write the file."
                    },
                    "content": {
                        "type": "string",
                        "description": "Content to write."
                    }
                },
                "required": ["path", "content"]
            }
        ),
        Tool(
            name="execute_command",
            description="Execute a shell command.",
            inputSchema={
                "type": "object",
                "properties": {
                    "command": {
                        "type": "string",
                        "description": "The command to execute."
                    }
                },
                "required": ["command"]
            }
        ),
    ]


@server.call_tool()
async def call_tool(name: str, arguments: dict[str, Any]) -> list[TextContent]:
    """Execute tool call by translating to HTTP request to mock service."""
    async with httpx.AsyncClient() as client:
        try:
            if name == "read_file":
                response = await client.post(
                    f"{FILE_OPS_SERVICE_URL}/tools/read_file",
                    json=arguments,
                    timeout=30.0
                )
                response.raise_for_status()
                result = response.json()
                return [TextContent(type="text", text=json.dumps(result, indent=2))]

            elif name == "write_file":
                response = await client.post(
                    f"{FILE_OPS_SERVICE_URL}/tools/write_file",
                    json=arguments,
                    timeout=30.0
                )
                response.raise_for_status()
                result = response.json()
                return [TextContent(type="text", text=json.dumps(result, indent=2))]

            elif name == "execute_command":
                response = await client.post(
                    f"{FILE_OPS_SERVICE_URL}/tools/execute_command",
                    json=arguments,
                    timeout=30.0
                )
                response.raise_for_status()
                result = response.json()
                return [TextContent(type="text", text=json.dumps(result, indent=2))]

            else:
                return [TextContent(type="text", text=f"Unknown tool: {name}")]

        except httpx.HTTPError as e:
            return [TextContent(type="text", text=f"Error calling file operations service: {e}")]
        except Exception as e:
            return [TextContent(type="text", text=f"Unexpected error: {e}")]


async def main():
    async with stdio_server() as (read_stream, write_stream):
        await server.run(
            read_stream,
            write_stream,
            server.create_initialization_options()
        )


if __name__ == "__main__":
    asyncio.run(main())