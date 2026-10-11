"""MCP Server for Gmail tools.

This server defines tool schemas and translates tool calls to HTTP requests
to the mock service (internal implementation detail, not exposed to Agent).

Tools: gmail_list_messages, gmail_get_message
"""

import json
import httpx
from mcp.server import Server
from mcp.server.stdio import stdio_server
from mcp.types import Tool, TextContent

# Create MCP server instance
server = Server("gmail")

# HTTP mock service base URL (internal - not exposed to agent)
HTTP_BASE_URL = "http://localhost:9100"

# Tool-to-endpoint mapping (internal)
TOOL_ENDPOINTS = {
    "gmail_list_messages": "/gmail/messages",
    "gmail_get_message": "/gmail/messages/get",
}


@server.list_tools()
async def list_tools() -> list[Tool]:
    """Return tool definitions matching the gmail schema."""
    return [
        Tool(
            name="gmail_list_messages",
            description="Get the list of messages in the inbox",
            inputSchema={
                "type": "object",
                "properties": {
                    "days_back": {
                        "type": "integer",
                        "description": "Fetch messages from the last N days",
                        "default": 7,
                    },
                    "max_results": {
                        "type": "integer",
                        "description": "Maximum number of results",
                        "default": 20,
                    },
                },
                "required": [],
            },
        ),
        Tool(
            name="gmail_get_message",
            description="Get the full details of a message by ID",
            inputSchema={
                "type": "object",
                "properties": {
                    "message_id": {
                        "type": "string",
                        "description": "The message ID",
                    },
                },
                "required": ["message_id"],
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