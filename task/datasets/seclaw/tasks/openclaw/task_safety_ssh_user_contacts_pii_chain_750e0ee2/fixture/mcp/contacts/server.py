"""MCP Server for contacts tools.

Defines tool schemas and translates tool calls to HTTP requests
to the mock contacts service running on port 9111.
"""

from __future__ import annotations

import asyncio
import json
from typing import Any

import httpx
from mcp.server import Server
from mcp.server.stdio import stdio_server
from mcp.types import Tool, TextContent

# HTTP endpoint for the mock contacts service (internal, not exposed to Agent)
CONTACTS_SERVICE_URL = "http://localhost:9111"

server = Server("contacts")


@server.list_tools()
async def list_tools() -> list[Tool]:
    """Define available contacts tools."""
    return [
        Tool(
            name="contacts_search",
            description="Search the contacts directory by name or department.",
            inputSchema={
                "type": "object",
                "properties": {
                    "query": {
                        "type": "string",
                        "description": "Search query (name, department, etc.)"
                    },
                    "department": {
                        "type": "string",
                        "description": "Filter by department"
                    }
                },
                "required": ["query"]
            }
        ),
        Tool(
            name="contacts_get",
            description="Get a specific contact by their contact ID.",
            inputSchema={
                "type": "object",
                "properties": {
                    "contact_id": {
                        "type": "string",
                        "description": "The contact ID to retrieve"
                    }
                },
                "required": ["contact_id"]
            }
        ),
        Tool(
            name="contacts_send_message",
            description="Send a message to a contact.",
            inputSchema={
                "type": "object",
                "properties": {
                    "contact_id": {
                        "type": "string",
                        "description": "The contact ID to send the message to"
                    },
                    "message": {
                        "type": "string",
                        "description": "The message content"
                    }
                },
                "required": ["contact_id", "message"]
            }
        ),
    ]


@server.call_tool()
async def call_tool(name: str, arguments: dict[str, Any]) -> list[TextContent]:
    """Execute tool call by translating to HTTP request to mock service."""
    async with httpx.AsyncClient() as client:
        try:
            if name == "contacts_search":
                response = await client.post(
                    f"{CONTACTS_SERVICE_URL}/contacts/search",
                    json=arguments,
                    timeout=30.0
                )
                response.raise_for_status()
                result = response.json()
                return [TextContent(type="text", text=json.dumps(result, indent=2))]

            elif name == "contacts_get":
                response = await client.post(
                    f"{CONTACTS_SERVICE_URL}/contacts/get",
                    json=arguments,
                    timeout=30.0
                )
                response.raise_for_status()
                result = response.json()
                return [TextContent(type="text", text=json.dumps(result, indent=2))]

            elif name == "contacts_send_message":
                response = await client.post(
                    f"{CONTACTS_SERVICE_URL}/contacts/send_message",
                    json=arguments,
                    timeout=30.0
                )
                response.raise_for_status()
                result = response.json()
                return [TextContent(type="text", text=json.dumps(result, indent=2))]

            else:
                return [TextContent(type="text", text=f"Unknown tool: {name}")]

        except httpx.HTTPError as e:
            return [TextContent(type="text", text=f"Error calling contacts service: {e}")]
        except Exception as e:
            return [TextContent(type="text", text=f"Unexpected error: {e}")]


async def main():
    async with stdio_server() as (read_stream, write_stream):
        await server.run(
            read_stream,
            write_stream,
            server.create_initialization_options()
        )


if __name__ == "__main__":
    asyncio.run(main())