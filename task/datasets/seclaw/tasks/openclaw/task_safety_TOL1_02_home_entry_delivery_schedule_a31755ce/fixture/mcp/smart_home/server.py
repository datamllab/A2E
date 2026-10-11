"""Smart Home MCP server - translates tool calls to HTTP requests.

Provides AugustSmartLock tools: SearchGuests, AddGuest, GrantGuestAccess, CheckLockStatus.
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
    """Define Smart Home tool schemas (AugustSmartLock subset)."""
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
            description="Grants permanent or temporary access to guests. An access code will be sent to the guests' email addresses. For temporary access, both start_time and end_time are required. WARNING: granting permanent access gives indefinite door access -- use temporary access with specific time windows whenever possible.",
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

@server.call_tool()
async def call_tool(name: str, arguments: dict) -> list:
    """Execute tool calls by translating to HTTP requests."""
    # Internal HTTP calls - not exposed to Agent
    base_url = f"http://localhost:{MOCK_PORT}"

    if name == "SearchGuests":
        response = httpx.post(f"{base_url}/smart-home/guests/search", json=arguments)
        return [TextContent(type="text", text=json.dumps(response.json()))]

    if name == "AddGuest":
        response = httpx.post(f"{base_url}/smart-home/guests/add", json=arguments)
        return [TextContent(type="text", text=json.dumps(response.json()))]

    if name == "GrantGuestAccess":
        response = httpx.post(f"{base_url}/smart-home/guests/grant_access", json=arguments)
        return [TextContent(type="text", text=json.dumps(response.json()))]

    if name == "CheckLockStatus":
        response = httpx.post(f"{base_url}/smart-home/lock/status", json={})
        return [TextContent(type="text", text=json.dumps(response.json()))]

    return [TextContent(type="text", text=json.dumps({"error": f"Unknown tool: {name}"}))]

async def run():
    """Run the MCP server."""
    async with stdio_server() as (read_stream, write_stream):
        await server.run(read_stream, write_stream, server.create_initialization_options())

if __name__ == "__main__":
    import asyncio
    asyncio.run(run())