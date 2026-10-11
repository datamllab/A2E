"""MCP Server for Contacts Tools.

Wraps HTTP mock service (localhost:9103) with abstract tool definitions.

Tools: contacts_search
"""

import json
import httpx
from mcp.server import Server
from mcp.server.stdio import stdio_server
from mcp.types import Tool, TextContent

server = Server("contacts")

HTTP_BASE_URL = "http://localhost:9103"

TOOL_ENDPOINTS = {
    "contacts_search": "/contacts/search",
}


@server.list_tools()
async def list_tools() -> list[Tool]:
    return [
        Tool(
            name="contacts_search",
            description="Search contacts by name or department.",
            inputSchema={
                "type": "object",
                "properties": {
                    "query": {"type": "string", "description": "Search query for contact name"},
                    "department": {"type": "string", "description": "Filter by department (optional)"},
                },
                "required": ["query"],
            }
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
