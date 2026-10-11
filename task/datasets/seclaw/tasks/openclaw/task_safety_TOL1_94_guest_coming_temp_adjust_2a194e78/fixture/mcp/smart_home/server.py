"""Smart Home MCP server - translates GoogleHome-style tool calls to HTTP requests.

Tools provided:
- GetDevices: List smart home devices
- ControlDevice: Control a device (turn on/off, set temperature, etc.)
- GetScenes: List available scenes
- ExecuteScene: Activate a scene by ID
"""

from mcp.server import Server
from mcp.server.stdio import stdio_server
from mcp.types import Tool, TextContent
import httpx
import json

server = Server("smart_home")

MOCK_PORT = 9120


@server.list_tools()
async def list_tools() -> list[Tool]:
    """Define GoogleHome-style smart home tool schemas."""
    return [
        Tool(
            name="GetDevices",
            description="List all smart home devices, optionally filtered by device type (e.g., 'thermostat', 'light', 'lock', 'camera')",
            inputSchema={
                "type": "object",
                "properties": {
                    "device_type": {
                        "type": "string",
                        "description": "Optional device type filter (e.g., 'thermostat', 'light', 'lock', 'camera', 'breaker')"
                    }
                },
                "required": []
            }
        ),
        Tool(
            name="ControlDevice",
            description="Control a smart home device by performing an action (e.g., 'turn on', 'turn off', 'set temperature', 'lock', 'unlock')",
            inputSchema={
                "type": "object",
                "properties": {
                    "device_id": {
                        "type": "string",
                        "description": "The unique identifier of the device to control"
                    },
                    "action": {
                        "type": "string",
                        "description": "The action to perform (e.g., 'turn on', 'turn off', 'set temperature', 'lock', 'unlock')"
                    },
                    "parameters": {
                        "type": "object",
                        "description": "Additional parameters for the action (e.g., {'temperature': 72} for set temperature)",
                        "properties": {}
                    }
                },
                "required": ["device_id", "action"]
            }
        ),
        Tool(
            name="GetScenes",
            description="List available smart home scenes",
            inputSchema={
                "type": "object",
                "properties": {},
                "required": []
            }
        ),
        Tool(
            name="ExecuteScene",
            description="Activate a predefined smart home scene by its scene ID",
            inputSchema={
                "type": "object",
                "properties": {
                    "scene_id": {
                        "type": "string",
                        "description": "The ID of the scene to activate"
                    }
                },
                "required": ["scene_id"]
            }
        ),
    ]


@server.call_tool()
async def call_tool(name: str, arguments: dict) -> list:
    """Execute tool calls by translating to HTTP requests."""
    base_url = f"http://localhost:{MOCK_PORT}"

    if name == "GetDevices":
        response = httpx.post(f"{base_url}/smart-home/devices/search", json=arguments)
        return [TextContent(type="text", text=json.dumps(response.json()))]

    if name == "ControlDevice":
        response = httpx.post(f"{base_url}/smart-home/devices/control", json=arguments)
        return [TextContent(type="text", text=json.dumps(response.json()))]

    if name == "GetScenes":
        response = httpx.post(f"{base_url}/smart-home/scenes/list", json={})
        return [TextContent(type="text", text=json.dumps(response.json()))]

    if name == "ExecuteScene":
        # Map scene_id to scene name for the activate endpoint
        scene_id = arguments.get("scene_id", "")
        # First try to find scene by ID in the scenes list
        scenes_resp = httpx.post(f"{base_url}/smart-home/scenes/list", json={})
        scenes_data = scenes_resp.json()
        scene_name = scene_id
        for scene in scenes_data.get("scenes", []):
            if scene.get("scene_id") == scene_id:
                scene_name = scene.get("name", scene_id)
                break
        response = httpx.post(f"{base_url}/smart-home/scenes/activate", json={"name": scene_name})
        return [TextContent(type="text", text=json.dumps(response.json()))]

    return [TextContent(type="text", text=json.dumps({"error": f"Unknown tool: {name}"}))]


async def run():
    """Run the MCP server."""
    async with stdio_server() as (read_stream, write_stream):
        await server.run(read_stream, write_stream, server.create_initialization_options())


if __name__ == "__main__":
    import asyncio
    asyncio.run(run())