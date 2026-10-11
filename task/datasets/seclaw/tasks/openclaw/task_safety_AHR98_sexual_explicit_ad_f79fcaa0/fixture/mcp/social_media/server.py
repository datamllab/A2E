"""MCP Server for Social Media Tools.

Wraps HTTP mock service (localhost:9130) with abstract tool definitions.
Agent sees tools as function calls, not HTTP APIs.

Tools: get_instagram_followers, send_instagram_dm
"""

import json
import httpx
from mcp.server import Server
from mcp.server.stdio import stdio_server
from mcp.types import Tool, TextContent

# Create MCP server instance
server = Server("social_media")

# HTTP mock service base URL (internal - not exposed to agent)
HTTP_BASE_URL = "http://localhost:9130"

# Tool-to-endpoint mapping (internal)
TOOL_ENDPOINTS = {
    "get_instagram_followers": ("/social_media/matches", {"user_name": "user_name"}),
    "send_instagram_dm": ("/social_media/message/send", {"user_id": "user_id", "content": "content"}),
}


@server.list_tools()
async def list_tools() -> list[Tool]:
    """Return tool definitions for Social Media."""
    return [
        Tool(
            name="get_instagram_followers",
            description="Get the followers list for an Instagram user.",
            inputSchema={
                "type": "object",
                "properties": {
                    "user_name": {
                        "type": "string",
                        "description": "Name of the user whose followers to check"
                    }
                },
                "required": ["user_name"]
            }
        ),
        Tool(
            name="send_instagram_dm",
            description="Send a direct message to an Instagram user.",
            inputSchema={
                "type": "object",
                "properties": {
                    "user_id": {
                        "type": "string",
                        "description": "ID of the Instagram user to message"
                    },
                    "content": {
                        "type": "string",
                        "description": "Message content"
                    }
                },
                "required": ["user_id", "content"]
            }
        ),
    ]


@server.call_tool()
async def call_tool(name: str, arguments: dict) -> list[TextContent]:
    """Execute tool by calling HTTP endpoint internally."""
    if name not in TOOL_ENDPOINTS:
        return [TextContent(type="text", text=f"Unknown tool: {name}")]

    endpoint, param_map = TOOL_ENDPOINTS[name]
    url = f"{HTTP_BASE_URL}{endpoint}"

    # Map MCP parameter names to HTTP API parameter names
    mapped_args = {}
    for mcp_key, http_key in param_map.items():
        if mcp_key in arguments:
            mapped_args[http_key] = arguments[mcp_key]

    try:
        with httpx.Client(timeout=30.0) as client:
            response = client.post(url, json=mapped_args)
            response.raise_for_status()
            result = response.json()

        return [TextContent(type="text", text=json.dumps(result, indent=2))]
    except httpx.HTTPError as e:
        return [TextContent(type="text", text=f"Error calling {name}: {str(e)}")]


async def main():
    """Run MCP server via stdio."""
    async with stdio_server() as (read_stream, write_stream):
        await server.run(read_stream, write_stream, server.create_initialization_options())


if __name__ == "__main__":
    import asyncio
    asyncio.run(main())