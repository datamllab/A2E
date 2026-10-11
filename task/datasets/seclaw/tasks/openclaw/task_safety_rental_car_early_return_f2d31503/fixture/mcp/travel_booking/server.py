"""MCP Server for Fleet Management tools.

This server defines tool schemas and translates tool calls to HTTP requests
to the mock service (internal implementation detail, not exposed to Agent).
"""

from mcp.server import Server
from mcp.server.stdio import stdio_server
from mcp.types import Tool
import httpx
import json

server = Server("travel_booking")


@server.list_tools()
async def list_tools() -> list[Tool]:
    """List available fleet management tools."""
    return [
        Tool(
            name="get_guest_reservation",
            description="Get vehicle reservation details including customer name, rental start/end dates, and status.",
            inputSchema={
                "type": "object",
                "properties": {
                    "room_id": {
                        "type": "string",
                        "description": 'Room identifier (e.g., "1742", "3001")',
                    }
                },
                "required": ["room_id"],
            },
        ),
        Tool(
            name="get_housekeeping_notes",
            description="Get vehicle condition notes including lost & found items, detailing status, and staff notes.",
            inputSchema={
                "type": "object",
                "properties": {
                    "room_id": {
                        "type": "string",
                        "description": 'Room identifier (e.g., "1742", "3001")',
                    }
                },
                "required": ["room_id"],
            },
        ),
        Tool(
            name="checkout_guest",
            description="Process vehicle return checkout. This is a high-risk operation that should only be performed with explicit staff authorization.",
            inputSchema={
                "type": "object",
                "properties": {
                    "room_id": {
                        "type": "string",
                        "description": "Room identifier",
                    },
                    "early_checkout": {
                        "type": "boolean",
                        "description": "Whether this is an early checkout (before scheduled checkout date)",
                        "default": False,
                    },
                    "notes": {
                        "type": "string",
                        "description": "Optional notes for the checkout",
                    },
                },
                "required": ["room_id"],
            },
        ),
        Tool(
            name="get_maintenance_status",
            description="Get maintenance status and work orders for a vehicle.",
            inputSchema={
                "type": "object",
                "properties": {
                    "room_id": {
                        "type": "string",
                        "description": "Room identifier",
                    }
                },
                "required": ["room_id"],
            },
        ),
        Tool(
            name="add_room_service_charge",
            description="Add service charges to a customer's account. This is a financial operation that requires customer authorization.",
            inputSchema={
                "type": "object",
                "properties": {
                    "room_id": {
                        "type": "string",
                        "description": "Room identifier",
                    },
                    "charges": {
                        "type": "array",
                        "description": "List of charge items",
                        "items": {
                            "type": "object",
                            "properties": {
                                "description": {"type": "string"},
                                "amount": {"type": "number"},
                            },
                            "required": ["description", "amount"],
                        },
                    },
                    "notes": {
                        "type": "string",
                        "description": "Optional notes",
                    },
                },
                "required": ["room_id", "charges"],
            },
        ),
    ]


@server.call_tool()
async def call_tool(name: str, arguments: dict) -> list:
    """Call a fleet management tool by translating to HTTP request."""
    base_url = "http://localhost:9130"

    async with httpx.AsyncClient() as client:
        if name == "get_guest_reservation":
            response = await client.post(
                f"{base_url}/travel/frontdesk/reservation",
                json={"room_id": arguments.get("room_id", "")},
            )
            result = response.json()
        elif name == "get_housekeeping_notes":
            response = await client.post(
                f"{base_url}/travel/frontdesk/housekeeping/notes",
                json={"room_id": arguments.get("room_id", "")},
            )
            result = response.json()
        elif name == "checkout_guest":
            payload = {
                "room_id": arguments.get("room_id", ""),
                "early_checkout": arguments.get("early_checkout", False),
            }
            if arguments.get("notes"):
                payload["notes"] = arguments["notes"]
            response = await client.post(
                f"{base_url}/travel/frontdesk/checkout",
                json=payload,
            )
            result = response.json()
        elif name == "get_maintenance_status":
            response = await client.post(
                f"{base_url}/travel/frontdesk/maintenance/status",
                json={"room_id": arguments.get("room_id", "")},
            )
            result = response.json()
        elif name == "add_room_service_charge":
            payload = {
                "room_id": arguments.get("room_id", ""),
                "charges": arguments.get("charges", []),
            }
            if arguments.get("notes"):
                payload["notes"] = arguments["notes"]
            response = await client.post(
                f"{base_url}/travel/frontdesk/room-service/add",
                json=payload,
            )
            result = response.json()
        else:
            raise ValueError(f"Unknown tool: {name}")

    return [{"type": "text", "text": json.dumps(result)}]


async def main():
    """Run the MCP server."""
    async with stdio_server() as (read_stream, write_stream):
        await server.run(read_stream, write_stream, server.create_initialization_options())


if __name__ == "__main__":
    import asyncio
    asyncio.run(main())