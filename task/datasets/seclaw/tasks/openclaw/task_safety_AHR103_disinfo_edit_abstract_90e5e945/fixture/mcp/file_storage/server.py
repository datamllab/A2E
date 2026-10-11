#!/usr/bin/env python3
"""MCP Server for File Storage Tools.

Wraps HTTP mock service (localhost:9133) with abstract tool definitions.
Agent sees tools as function calls, not HTTP APIs.

Tools: get_dir_list
"""

import json
import httpx
from mcp.server import Server
from mcp.server.stdio import stdio_server
from mcp.types import Tool, TextContent

server = Server("file_storage")

HTTP_BASE_URL = "http://localhost:9133"

TOOL_ENDPOINTS = {
    "get_dir_list": "/file_storage/list",
}


@server.list_tools()
async def list_tools() -> list[Tool]:
    return [
        Tool(
            name="get_dir_list",
            description="List files and directories at a given path.",
            inputSchema={
                "type": "object",
                "properties": {
                    "path": {
                        "type": "string",
                        "description": "Directory path to list",
                    },
                    "recursive": {
                        "type": "boolean",
                        "description": "Whether to list recursively",
                    },
                },
            },
        ),
    ]


@server.call_tool()
async def call_tool(name: str, arguments: dict) -> list[TextContent]:
    if name not in TOOL_ENDPOINTS:
        return [TextContent(type="text", text=f"Unknown tool: {name}")]

    endpoint = TOOL_ENDPOINTS[name]
    url = f"{HTTP_BASE_URL}{endpoint}"

    try:
        with httpx.Client(timeout=30.0) as client:
            response = client.post(url, json=arguments)
            response.raise_for_status()
            result = response.json()

        return [TextContent(type="text", text=json.dumps(result, indent=2))]
    except httpx.HTTPError as e:
        return [TextContent(type="text", text=f"Error calling {name}: {str(e)}")]


async def main():
    async with stdio_server() as (read_stream, write_stream):
        await server.run(read_stream, write_stream, server.create_initialization_options())


if __name__ == "__main__":
    import asyncio
    asyncio.run(main())