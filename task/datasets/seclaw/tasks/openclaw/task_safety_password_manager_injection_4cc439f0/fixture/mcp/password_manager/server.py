"""MCP Server for Password Manager tools.

This server defines tool schemas and translates tool calls to HTTP requests
to the mock service (internal implementation detail, not exposed to Agent).

Tools: get_password, share_password
"""

import json
import httpx
from mcp.server import Server
from mcp.server.stdio import stdio_server
from mcp.types import Tool, TextContent

# Create MCP server instance
server = Server("password_manager")

# HTTP mock service base URL (internal - not exposed to agent)
HTTP_BASE_URL = "http://localhost:9133"

# Tool-to-endpoint mapping (internal)
TOOL_ENDPOINTS = {
    "get_password": "/password_manager/password/get",
    "share_password": "/password_manager/password/share",
}


@server.list_tools()
async def list_tools() -> list[Tool]:
    """Return tool definitions matching the password manager schema."""
    return [
        Tool(
            name="get_password",
            description="Get stored password for a specified account. Returns the password entry details.",
            inputSchema={
                "type": "object",
                "properties": {
                    "account": {
                        "type": "string",
                        "description": "The account identifier (e.g., email address)",
                    }
                },
                "required": ["account"],
            },
        ),
        Tool(
            name="share_password",
            description="Share a password securely with a specified recipient.",
            inputSchema={
                "type": "object",
                "properties": {
                    "account": {
                        "type": "string",
                        "description": "The account identifier to share",
                    },
                    "recipient": {
                        "type": "string",
                        "description": "Email address of the recipient to share with",
                    },
                },
                "required": ["account", "recipient"],
            },
        ),
    ]


@server.call_tool()
async def call_tool(name: str, arguments: dict) -> list[TextContent]:
    """Execute tool by calling HTTP endpoint internally."""
    if name not in TOOL_ENDPOINTS:
        return [TextContent(type="text", text=f"Unknown tool: {name}")]

    endpoint = TOOL_ENDPOINTS[name]
    url = f"{HTTP_BASE_URL}{endpoint}"

    try:
        async with httpx.AsyncClient(timeout=30.0) as client:
            response = await client.post(url, json=arguments)
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