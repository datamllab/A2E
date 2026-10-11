"""MCP server for helpdesk service."""

import json
import httpx
from mcp.server import Server
from mcp.server.stdio import stdio_server
from mcp.types import Tool, TextContent

SERVER_NAME = "helpdesk"
PORT = 9107
BASE_URL = f"http://localhost:{PORT}"

server = Server(SERVER_NAME)


@server.list_tools()
async def list_tools() -> list[Tool]:
    return [
        Tool(
            name="helpdesk_list_tickets",
            description="List helpdesk tickets with optional status filter",
            inputSchema={
                "type": "object",
                "properties": {
                    "status": {
                        "type": "string",
                        "description": "Filter by status (open/closed/all)",
                        "default": "open",
                    },
                },
                "required": [],
            },
        ),
        Tool(
            name="helpdesk_get_ticket",
            description="Get detailed information about a specific helpdesk ticket",
            inputSchema={
                "type": "object",
                "properties": {
                    "ticket_id": {
                        "type": "string",
                        "description": "Ticket ID",
                    },
                },
                "required": ["ticket_id"],
            },
        ),
        Tool(
            name="helpdesk_update_ticket",
            description="Update a helpdesk ticket's priority, tags, or category",
            inputSchema={
                "type": "object",
                "properties": {
                    "ticket_id": {
                        "type": "string",
                        "description": "Ticket ID",
                    },
                    "priority": {
                        "type": "string",
                        "description": "Priority level (low/medium/high/critical)",
                    },
                    "tags": {
                        "type": "array",
                        "items": {"type": "string"},
                        "description": "Tag list",
                    },
                    "category": {
                        "type": "string",
                        "description": "Ticket category",
                    },
                },
                "required": ["ticket_id"],
            },
        ),
    ]


@server.call_tool()
async def call_tool(name: str, arguments: dict):
    async with httpx.AsyncClient(timeout=30.0) as client:
        if name == "helpdesk_list_tickets":
            resp = await client.post(f"{BASE_URL}/helpdesk/tickets", json=arguments)
        elif name == "helpdesk_get_ticket":
            resp = await client.post(f"{BASE_URL}/helpdesk/tickets/get", json=arguments)
        elif name == "helpdesk_update_ticket":
            resp = await client.post(f"{BASE_URL}/helpdesk/tickets/update", json=arguments)
        else:
            return [TextContent(type="text", text=json.dumps({"error": f"Unknown tool: {name}"}))]

        return [TextContent(type="text", text=json.dumps(resp.json(), indent=2))]


async def main():
    async with stdio_server() as (read_stream, write_stream):
        await server.run(read_stream, write_stream, server.create_initialization_options())


if __name__ == "__main__":
    import asyncio
    asyncio.run(main())