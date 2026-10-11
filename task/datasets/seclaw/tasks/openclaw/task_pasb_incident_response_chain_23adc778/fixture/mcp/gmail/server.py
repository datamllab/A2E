"""MCP Server for Gmail tools.

Defines tool schemas and translates tool calls to HTTP requests
to the mock Gmail service running on port 9100.
"""

from __future__ import annotations

import asyncio
import json
from typing import Any

import httpx
from mcp.server import Server
from mcp.server.stdio import stdio_server
from mcp.types import Tool, TextContent

# HTTP endpoint for the mock Gmail service (internal, not exposed to Agent)
GMAIL_SERVICE_URL = "http://localhost:9100"

server = Server("gmail")


@server.list_tools()
async def list_tools() -> list[Tool]:
    """Define available Gmail tools."""
    return [
        Tool(
            name="list_emails",
            description="List recent emails from inbox, filtered by recency.",
            inputSchema={
                "type": "object",
                "properties": {
                    "days_back": {
                        "type": "integer",
                        "description": "Number of days to look back (default 7).",
                        "default": 7
                    },
                    "max_results": {
                        "type": "integer",
                        "description": "Maximum number of results to return (default 20).",
                        "default": 20
                    }
                },
                "required": []
            }
        ),
        Tool(
            name="read_email",
            description="Read the full content of a specific email by message ID.",
            inputSchema={
                "type": "object",
                "properties": {
                    "message_id": {
                        "type": "string",
                        "description": "The message ID to read."
                    }
                },
                "required": ["message_id"]
            }
        ),
    ]


@server.call_tool()
async def call_tool(name: str, arguments: dict[str, Any]) -> list[TextContent]:
    """Execute tool call by translating to HTTP request to mock service."""
    async with httpx.AsyncClient() as client:
        try:
            if name == "list_emails":
                response = await client.post(
                    f"{GMAIL_SERVICE_URL}/gmail/messages",
                    json=arguments,
                    timeout=30.0
                )
                response.raise_for_status()
                result = response.json()
                return [TextContent(type="text", text=json.dumps(result, indent=2))]

            elif name == "read_email":
                response = await client.post(
                    f"{GMAIL_SERVICE_URL}/gmail/messages/get",
                    json=arguments,
                    timeout=30.0
                )
                response.raise_for_status()
                result = response.json()
                return [TextContent(type="text", text=json.dumps(result, indent=2))]

            else:
                return [TextContent(type="text", text=f"Unknown tool: {name}")]

        except httpx.HTTPError as e:
            return [TextContent(type="text", text=f"Error calling Gmail service: {e}")]
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