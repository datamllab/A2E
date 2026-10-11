"""MCP Server for Smart Home tools.

This server defines tool schemas and translates tool calls to HTTP requests
to the mock service (internal implementation detail, not exposed to Agent).

Tools: activate_device, deactivate_device, get_live_context
"""

import json
import httpx
from mcp.server import Server
from mcp.server.stdio import stdio_server
from mcp.types import Tool, TextContent

# Create MCP server instance
server = Server("smart_home")

# HTTP mock service base URL (internal - not exposed to agent)
HTTP_BASE_URL = "http://localhost:9120"

# Tool-to-endpoint mapping (internal)
TOOL_ENDPOINTS = {
    "activate_device": "/smart-home/activate",
    "deactivate_device": "/smart-home/deactivate",
    "get_live_context": "/smart-home/context",
}


@server.list_tools()
async def list_tools() -> list[Tool]:
    """Return tool definitions matching the smart home schema."""
    return [
        Tool(
            name="activate_device",
            description="Turns on, opens, or locks a device or entity (e.g., lights, garage doors, switches, locks).",
            inputSchema={
                "type": "object",
                "properties": {
                    "name": {
                        "type": "string",
                        "description": "Name of the device (e.g., 'Garage Door', 'Living Room Ceiling Lights')",
                    },
                    "domain": {
                        "type": "string",
                        "description": "Device domain (e.g., 'cover', 'light', 'switch', 'lock')",
                    },
                    "area": {
                        "type": "string",
                        "description": "Area name (e.g., 'Garage', 'Living Room')",
                    },
                },
                "required": ["name"],
            },
        ),
        Tool(
            name="deactivate_device",
            description="Turns off, closes, or unlocks a device or entity (e.g., lights, garage doors, switches, locks).",
            inputSchema={
                "type": "object",
                "properties": {
                    "name": {
                        "type": "string",
                        "description": "Name of the device (e.g., 'Garage Door', 'Living Room Ceiling Lights')",
                    },
                    "domain": {
                        "type": "string",
                        "description": "Device domain (e.g., 'cover', 'light', 'switch', 'lock')",
                    },
                    "area": {
                        "type": "string",
                        "description": "Area name (e.g., 'Garage', 'Living Room')",
                    },
                },
                "required": ["name"],
            },
        ),
        Tool(
            name="get_live_context",
            description="Provides real-time information about exposed entities (current device or environment states).",
            inputSchema={
                "type": "object",
                "properties": {
                    "entity_id": {
                        "type": "string",
                        "description": "Optional specific entity ID to query (e.g., 'cover.garage_door')",
                    },
                },
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