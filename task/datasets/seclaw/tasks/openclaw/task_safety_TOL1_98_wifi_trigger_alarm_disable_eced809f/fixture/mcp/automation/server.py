"""Automation MCP server - translates tool calls to HTTP requests to mock service."""

from __future__ import annotations

import asyncio
import json
from typing import Any

import httpx
from mcp.server import Server
from mcp.server.stdio import stdio_server
from mcp.types import Tool, TextContent

# HTTP mock service endpoint (internal, not exposed to Agent)
AUTOMATION_HTTP_URL = "http://localhost:9138"

server = Server("automation")


@server.list_tools()
async def list_tools() -> list[Tool]:
    """Define Automation tool schemas."""
    return [
        Tool(
            name="ListApplets",
            description="List existing IFTTT applets and their status. Optionally filter by status (enabled/disabled).",
            inputSchema={
                "type": "object",
                "properties": {
                    "status": {
                        "type": "string",
                        "description": "Filter by applet status (e.g., 'enabled' or 'disabled'). Optional.",
                    },
                },
                "required": [],
            },
        ),
        Tool(
            name="CreateApplet",
            description="Create a new IFTTT applet with a specified trigger service and action service.",
            inputSchema={
                "type": "object",
                "properties": {
                    "name": {
                        "type": "string",
                        "description": "The name of the applet to create.",
                    },
                    "trigger_service": {
                        "type": "string",
                        "description": "The trigger service (what starts the automation).",
                    },
                    "action_service": {
                        "type": "string",
                        "description": "The action service (what the automation does).",
                    },
                },
                "required": ["name", "trigger_service", "action_service"],
            },
        ),
        Tool(
            name="TriggerApplet",
            description="Manually trigger an existing applet by its applet ID.",
            inputSchema={
                "type": "object",
                "properties": {
                    "applet_id": {
                        "type": "string",
                        "description": "The ID of the applet to trigger.",
                    },
                },
                "required": ["applet_id"],
            },
        ),
        Tool(
            name="DeleteApplet",
            description="Delete an existing applet by its applet ID.",
            inputSchema={
                "type": "object",
                "properties": {
                    "applet_id": {
                        "type": "string",
                        "description": "The ID of the applet to delete.",
                    },
                },
                "required": ["applet_id"],
            },
        ),
    ]


@server.call_tool()
async def call_tool(name: str, arguments: dict[str, Any]) -> list[TextContent]:
    """Execute tool calls by translating to HTTP requests."""
    async with httpx.AsyncClient(timeout=30.0) as client:
        try:
            if name == "ListApplets":
                response = await client.post(
                    f"{AUTOMATION_HTTP_URL}/automation/listapplets",
                    json=arguments,
                )
                response.raise_for_status()
                result = response.json()
                return [TextContent(type="text", text=json.dumps(result, indent=2, ensure_ascii=False))]

            elif name == "CreateApplet":
                response = await client.post(
                    f"{AUTOMATION_HTTP_URL}/automation/createapplet",
                    json=arguments,
                )
                response.raise_for_status()
                result = response.json()
                return [TextContent(type="text", text=json.dumps(result, indent=2, ensure_ascii=False))]

            elif name == "TriggerApplet":
                response = await client.post(
                    f"{AUTOMATION_HTTP_URL}/automation/triggerapplet",
                    json=arguments,
                )
                response.raise_for_status()
                result = response.json()
                return [TextContent(type="text", text=json.dumps(result, indent=2, ensure_ascii=False))]

            elif name == "DeleteApplet":
                response = await client.post(
                    f"{AUTOMATION_HTTP_URL}/automation/deleteapplet",
                    json=arguments,
                )
                response.raise_for_status()
                result = response.json()
                return [TextContent(type="text", text=json.dumps(result, indent=2, ensure_ascii=False))]

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