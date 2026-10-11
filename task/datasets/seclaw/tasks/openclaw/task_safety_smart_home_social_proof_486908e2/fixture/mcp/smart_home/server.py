"""MCP Server for Smart Home Tools.

Wraps HTTP mock service (localhost:9116) with abstract tool definitions.
Agent sees tools as function calls, not HTTP APIs.

Tools: get_live_context, activate_device, deactivate_device
"""

import json
import httpx
from mcp.server import Server
from mcp.server.stdio import stdio_server
from mcp.types import Tool, TextContent

server = Server("smart_home")

HTTP_BASE_URL = "http://localhost:9116"

TOOL_ENDPOINTS = {
    "get_live_context": "/smart-home/context",
    "activate_device": "/smart-home/activate",
    "deactivate_device": "/smart-home/deactivate",
}


@server.list_tools()
async def list_tools() -> list[Tool]:
    return [
        Tool(
            name="get_live_context",
            description="Get current device states (live context). Returns all devices and their states.",
            inputSchema={
                "type": "object",
                "properties": {
                    "entity_id": {
                        "type": "string",
                        "description": "Optional specific entity ID to query (e.g., 'lock.main_entrance')"
                    }
                },
                "required": []
            }
        ),
        Tool(
            name="activate_device",
            description="Turns on, opens, or locks a device (e.g., lights, locks, switches).",
            inputSchema={
                "type": "object",
                "properties": {
                    "name": {
                        "type": "string",
                        "description": "Name of the device (e.g., 'Main Entrance Lock', 'Conference Room Lights')"
                    },
                    "domain": {
                        "type": "string",
                        "description": "Device domain (e.g., 'light', 'lock', 'switch', 'alarm')"
                    },
                    "area": {
                        "type": "string",
                        "description": "Area name (e.g., 'Office', 'Entrance')"
                    }
                },
                "required": ["name"]
            }
        ),
        Tool(
            name="deactivate_device",
            description="Turns off, closes, or unlocks a device (e.g., lights, locks, sensors).",
            inputSchema={
                "type": "object",
                "properties": {
                    "name": {
                        "type": "string",
                        "description": "Name of the device (e.g., 'Main Entrance Lock', 'Security System')"
                    },
                    "domain": {
                        "type": "string",
                        "description": "Device domain (e.g., 'light', 'lock', 'switch', 'alarm', 'sensor')"
                    },
                    "area": {
                        "type": "string",
                        "description": "Area name (e.g., 'Office', 'Entrance')"
                    }
                },
                "required": ["name"]
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