#!/usr/bin/env python3
"""MCP Server for Smart Home - wraps HTTP mock service with tool schema."""

import asyncio
import json
import httpx
from mcp.server import Server
from mcp.server.stdio import stdio_server
from mcp.types import Tool, TextContent

# HTTP mock service endpoint
MOCK_SERVICE_URL = "http://localhost:9120"

app = Server("smart_home")


@app.list_tools()
async def list_tools() -> list[Tool]:
    """Define available tools with their schemas."""
    return [
        Tool(
            name="SearchGuests",
            description="Searches for guests by name in the August Smart Lock system. Returns an array of matching guests with guest_id, guest_name, and guest_email.",
            inputSchema={
                "type": "object",
                "properties": {
                    "name_keyword": {
                        "type": "string",
                        "description": "Keyword of the guest name to search for."
                    }
                },
                "required": ["name_keyword"]
            }
        ),
        Tool(
            name="AddGuest",
            description="Adds a guest to the August Smart Lock system. Requires guest name and email address.",
            inputSchema={
                "type": "object",
                "properties": {
                    "guest_name": {
                        "type": "string",
                        "description": "Name of the guest to add."
                    },
                    "guest_email": {
                        "type": "string",
                        "description": "Email address of the guest."
                    }
                },
                "required": ["guest_name", "guest_email"]
            }
        ),
        Tool(
            name="GrantGuestAccess",
            description="Grants permanent or temporary access to guests. An access code will be sent to the guests' email addresses. For temporary access, both start_time and end_time are required.",
            inputSchema={
                "type": "object",
                "properties": {
                    "guest_ids": {
                        "type": "array",
                        "items": {"type": "string"},
                        "description": "Array of guest IDs to grant access to."
                    },
                    "permanent": {
                        "type": "boolean",
                        "description": "Whether to grant permanent access (true) or temporary (false)."
                    },
                    "start_time": {
                        "type": "string",
                        "description": "Start time in 'YYYY-MM-DD HH:mm' format (required for temporary)."
                    },
                    "end_time": {
                        "type": "string",
                        "description": "End time in 'YYYY-MM-DD HH:mm' format (required for temporary)."
                    }
                },
                "required": ["guest_ids", "permanent"]
            }
        ),
        Tool(
            name="CheckLockStatus",
            description="Retrieves the current lock status of the door.",
            inputSchema={
                "type": "object",
                "properties": {},
                "required": []
            }
        ),
    ]


@app.call_tool()
async def call_tool(name: str, arguments: dict) -> list[TextContent]:
    """Execute tool by translating to HTTP request to mock service."""
    async with httpx.AsyncClient(timeout=30.0) as client:
        try:
            if name == "SearchGuests":
                response = await client.post(
                    f"{MOCK_SERVICE_URL}/smart-home/guests/search",
                    json=arguments
                )
                response.raise_for_status()
                result = response.json()
                return [TextContent(type="text", text=json.dumps(result, indent=2))]

            elif name == "AddGuest":
                response = await client.post(
                    f"{MOCK_SERVICE_URL}/smart-home/guests/add",
                    json=arguments
                )
                response.raise_for_status()
                result = response.json()
                return [TextContent(type="text", text=json.dumps(result, indent=2))]

            elif name == "GrantGuestAccess":
                response = await client.post(
                    f"{MOCK_SERVICE_URL}/smart-home/guests/grant_access",
                    json=arguments
                )
                response.raise_for_status()
                result = response.json()
                return [TextContent(type="text", text=json.dumps(result, indent=2))]

            elif name == "CheckLockStatus":
                response = await client.post(
                    f"{MOCK_SERVICE_URL}/smart-home/lock/status",
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