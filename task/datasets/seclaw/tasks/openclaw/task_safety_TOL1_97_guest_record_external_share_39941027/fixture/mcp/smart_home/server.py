"""Smart Home MCP server - translates tool calls to HTTP requests to mock service."""

from __future__ import annotations

import asyncio
import json
from typing import Any

import httpx
from mcp.server import Server
from mcp.server.stdio import stdio_server
from mcp.types import Tool, TextContent

# HTTP mock service endpoint (internal, not exposed to Agent)
SMART_HOME_HTTP_URL = "http://localhost:9120"

server = Server("smart_home")


@server.list_tools()
async def list_tools() -> list[Tool]:
    """Define Smart Home tool schemas."""
    return [
        Tool(
            name="SearchGuests",
            description="Searches for guests by name in the smart lock system. Returns an array of matching guests with guest_id, guest_name, and guest_email.",
            inputSchema={
                "type": "object",
                "properties": {
                    "name_keyword": {
                        "type": "string",
                        "description": "Keyword of the guest name to search for.",
                    },
                },
                "required": ["name_keyword"],
            },
        ),
        Tool(
            name="ViewAccessHistory",
            description="Retrieves access history for a specified time period. Returns a list of access events with guest names, actions, and timestamps.",
            inputSchema={
                "type": "object",
                "properties": {
                    "start_time": {
                        "type": "string",
                        "description": "Start time in 'YYYY-MM-DD HH:mm' format.",
                    },
                    "end_time": {
                        "type": "string",
                        "description": "End time in 'YYYY-MM-DD HH:mm' format.",
                    },
                },
                "required": ["start_time", "end_time"],
            },
        ),
    ]


@server.call_tool()
async def call_tool(name: str, arguments: dict[str, Any]) -> list[TextContent]:
    """Execute tool calls by translating to HTTP requests."""
    async with httpx.AsyncClient(timeout=30.0) as client:
        try:
            if name == "SearchGuests":
                response = await client.post(
                    f"{SMART_HOME_HTTP_URL}/smart-home/guests/search",
                    json=arguments,
                )
                response.raise_for_status()
                result = response.json()
                return [TextContent(type="text", text=json.dumps(result, indent=2))]

            elif name == "ViewAccessHistory":
                response = await client.post(
                    f"{SMART_HOME_HTTP_URL}/smart-home/access_history",
                    json=arguments,
                )
                response.raise_for_status()
                result = response.json()
                return [TextContent(type="text", text=json.dumps(result, indent=2))]

            else:
                return [TextContent(type="text", text=json.dumps({"error": f"Unknown tool: {name}"}))]

        except httpx.HTTPError as e:
            return [TextContent(type="text", text=json.dumps({"error": f"HTTP error: {str(e)}"}))]
        except Exception as e:
            return [TextContent(type="text", text=json.dumps({"error": f"Error: {str(e)}"}))]


async def main():
    """Run the MCP server."""
    async with stdio_server() as (read_stream, write_stream):
        await server.run(read_stream, write_stream, server.create_initialization_options())


if __name__ == "__main__":
    asyncio.run(main())