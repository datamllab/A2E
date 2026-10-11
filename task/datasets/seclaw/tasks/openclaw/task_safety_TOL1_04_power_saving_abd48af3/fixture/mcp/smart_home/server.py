#!/usr/bin/env python3
"""MCP Server for Smart Home - wraps HTTP mock service with tool schema."""

import asyncio
import json
import httpx
from mcp.server import Server
from mcp.server.stdio import stdio_server
from mcp.types import Tool, TextContent

# HTTP mock service endpoint (internal, not exposed to agent)
MOCK_SERVICE_URL = "http://localhost:9120"

app = Server("smart_home")


@app.list_tools()
async def list_tools() -> list[Tool]:
    """Define available tools with their schemas."""
    return [
        Tool(
            name="SearchDevices",
            description="Searches for smart home devices connected to Google Home. Returns a list of devices, each containing 'device_id', 'device_name', 'device_type' (e.g., 'light', 'thermostat', 'camera', 'alarm', 'appliance', 'sensor', 'switch'), and 'device_status' (including current state and area).",
            inputSchema={
                "type": "object",
                "properties": {
                    "device_type": {
                        "type": "string",
                        "description": "The type of device to search for (e.g., 'light', 'thermostat', 'camera'). If not specified, returns all connected devices."
                    }
                }
            }
        ),
        Tool(
            name="ListDeviceActions",
            description="Retrieves a list of possible actions that can be performed on a specified smart home device. Returns action_name, action_description, and action_parameters for each available action.",
            inputSchema={
                "type": "object",
                "properties": {
                    "device_id": {
                        "type": "string",
                        "description": "The unique identifier of the smart home device."
                    }
                },
                "required": ["device_id"]
            }
        ),
        Tool(
            name="ControlDevice",
            description="Controls a specified smart home device by turning it on/off, adjusting its settings, or performing other actions. The available actions depend on the device type (use ListDeviceActions to check).",
            inputSchema={
                "type": "object",
                "properties": {
                    "device_id": {
                        "type": "string",
                        "description": "The unique identifier of the smart home device to control."
                    },
                    "action": {
                        "type": "string",
                        "description": "The action to perform on the device (e.g., 'turn on', 'turn off', 'set temperature'). Must match the actions returned by ListDeviceActions for the specified device."
                    },
                    "parameters": {
                        "type": "object",
                        "description": "Additional parameters for the action (e.g., temperature value, brightness level). Required for some actions like 'set temperature'."
                    }
                },
                "required": ["device_id", "action"]
            }
        )
    ]


@app.call_tool()
async def call_tool(name: str, arguments: dict) -> list[TextContent]:
    """Execute tool by translating to HTTP request to mock service."""
    async with httpx.AsyncClient(timeout=30.0) as client:
        try:
            if name == "SearchDevices":
                response = await client.post(
                    f"{MOCK_SERVICE_URL}/smart-home/devices/search",
                    json=arguments
                )
                response.raise_for_status()
                result = response.json()
                return [TextContent(type="text", text=json.dumps(result, indent=2))]

            elif name == "ListDeviceActions":
                response = await client.post(
                    f"{MOCK_SERVICE_URL}/smart-home/devices/actions",
                    json=arguments
                )
                response.raise_for_status()
                result = response.json()
                return [TextContent(type="text", text=json.dumps(result, indent=2))]

            elif name == "ControlDevice":
                response = await client.post(
                    f"{MOCK_SERVICE_URL}/smart-home/devices/control",
                    json=arguments
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
    async with stdio_server() as (read_stream, write_stream):
        await app.run(
            read_stream,
            write_stream,
            app.create_initialization_options()
        )


if __name__ == "__main__":
    asyncio.run(main())