#!/usr/bin/env python3
"""MCP Server for Social Media Tools.

Wraps HTTP mock service (localhost:9130) with abstract tool definitions.
Agent sees tools as function calls, not HTTP APIs.

Tools: post_on_x
"""

import json
import httpx
from mcp.server import Server
from mcp.server.stdio import stdio_server
from mcp.types import Tool, TextContent

server = Server("social_media")

HTTP_BASE_URL = "http://localhost:9130"

TOOL_ENDPOINTS = {
    "post_on_x": "/social_media/post/create",
}


@server.list_tools()
async def list_tools() -> list[Tool]:
    return [
        Tool(
            name="post_on_x",
            description="Post content on X (Twitter).",
            inputSchema={
                "type": "object",
                "properties": {
                    "content": {
                        "type": "string",
                        "description": "Post content",
                    },
                    "platform": {
                        "type": "string",
                        "description": "Platform identifier",
                    },
                },
                "required": ["content"],
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