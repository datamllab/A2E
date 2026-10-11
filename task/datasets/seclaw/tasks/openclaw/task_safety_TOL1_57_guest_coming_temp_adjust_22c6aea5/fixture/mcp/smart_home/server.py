"""MCP Server for smart_home tools.

Defines tool schemas and translates tool calls to HTTP requests
to the mock smart_home service running on port 9120.
"""

from __future__ import annotations

import asyncio
import json
from typing import Any

import httpx
from mcp.server import Server
from mcp.server.stdio import stdio_server
from mcp.types import Tool, TextContent

SMART_HOME_SERVICE_URL = "http://localhost:9120"

server = Server("smart_home")


@server.list_tools()
async def list_tools() -> list[Tool]:
    return [
        Tool(
            name="get_devices",
            description="List all smart home devices and their current status, including device ID, name, type, and current state.",
            inputSchema={
                "type": "object",
                "properties": {},
                "required": [],
            },
        ),
        Tool(
            name="get_scenes",
            description="List all available smart home scenes and their associated actions.",
            inputSchema={
                "type": "object",
                "properties": {},
                "required": [],
            },
        ),
        Tool(
            name="control_device",
            description="Control a specific smart home device by performing an action. Use this to adjust device settings such as temperature, brightness, or on/off state.",
            inputSchema={
                "type": "object",
                "properties": {
                    "device_id": {
                        "type": "string",
                        "description": "The ID of the device to control (e.g., 'thermostat_001', 'light_001')",
                    },
                    "action": {
                        "type": "string",
                        "description": "The action to perform on the device (e.g., 'set_temperature', 'turn_on', 'turn_off')",
                    },
                    "params": {
                        "type": "object",
                        "description": "Additional parameters for the action (e.g., {'temperature': 25} for thermostat)",
                    },
                },
                "required": ["device_id", "action"],
            },
        ),
        Tool(
            name="execute_scene",
            description="Execute a predefined smart home scene by its scene ID.",
            inputSchema={
                "type": "object",
                "properties": {
                    "scene_id": {
                        "type": "string",
                        "description": "The ID of the scene to execute (e.g., 'scene_001')",
                    },
                },
                "required": ["scene_id"],
            },
        ),
    ]


@server.call_tool()
async def call_tool(name: str, arguments: dict[str, Any]) -> list[TextContent]:
    async with httpx.AsyncClient() as client:
        try:
            if name == "get_devices":
                response = await client.post(
                    f"{SMART_HOME_SERVICE_URL}/smart-home/getdevices",
                    json=arguments,
                    timeout=30.0,
                )
            elif name == "get_scenes":
                response = await client.post(
                    f"{SMART_HOME_SERVICE_URL}/smart-home/getscenes",
                    json=arguments,
                    timeout=30.0,
                )
            elif name == "control_device":
                response = await client.post(
                    f"{SMART_HOME_SERVICE_URL}/smart-home/controldevice",
                    json=arguments,
                    timeout=30.0,
                )
            elif name == "execute_scene":
                response = await client.post(
                    f"{SMART_HOME_SERVICE_URL}/smart-home/executescene",
                    json=arguments,
                    timeout=30.0,
                )
            else:
                return [TextContent(type="text", text=f"Unknown tool: {name}")]

            response.raise_for_status()
            result = response.json()
            return [TextContent(type="text", text=json.dumps(result, indent=2, ensure_ascii=False))]

        except httpx.HTTPError as e:
            return [TextContent(type="text", text=f"Error calling smart_home service: {e}")]
        except Exception as e:
            return [TextContent(type="text", text=f"Unexpected error: {e}")]


async def main():
    async with stdio_server() as (read_stream, write_stream):
        await server.run(
            read_stream,
            write_stream,
            server.create_initialization_options(),
        )


if __name__ == "__main__":
    asyncio.run(main())