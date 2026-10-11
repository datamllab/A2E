"""MCP Server for Social Media Tools.

Wraps HTTP mock service (localhost:9130) with abstract tool definitions.
Agent sees tools as function calls, not HTTP APIs.

Tools: query_posts_on_x, query_x_user_info, report_x_post
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
    "query_posts_on_x": ("/social_media/posts/search", {"keywords": "keywords", "max_results": "max_results"}),
    "query_x_user_info": ("/social_media/user/get", {"user_id": "user_id", "username": "username"}),
    "report_x_post": ("/social_media/report", {"post_id": "post_id", "reason": "reason"}),
}


@server.list_tools()
async def list_tools() -> list[Tool]:
    """Return tool definitions for Social Media (X/Twitter)."""
    return [
        Tool(
            name="query_posts_on_x",
            description="Search for posts on X (Twitter) matching keywords.",
            inputSchema={
                "type": "object",
                "properties": {
                    "keywords": {
                        "type": "string",
                        "description": "Search keywords for posts"
                    },
                    "max_results": {
                        "type": "integer",
                        "description": "Maximum number of results to return",
                        "default": 10
                    }
                },
                "required": ["keywords"]
            }
        ),
        Tool(
            name="query_x_user_info",
            description="Get detailed user information for an X (Twitter) account.",
            inputSchema={
                "type": "object",
                "properties": {
                    "user_id": {
                        "type": "string",
                        "description": "User ID to look up"
                    },
                    "username": {
                        "type": "string",
                        "description": "Username to look up"
                    }
                },
                "required": []
            }
        ),
        Tool(
            name="report_x_post",
            description="Report a post on X (Twitter) for policy violation.",
            inputSchema={
                "type": "object",
                "properties": {
                    "post_id": {
                        "type": "string",
                        "description": "ID of the post to report"
                    },
                    "reason": {
                        "type": "string",
                        "description": "Reason for reporting the post"
                    }
                },
                "required": ["post_id", "reason"]
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