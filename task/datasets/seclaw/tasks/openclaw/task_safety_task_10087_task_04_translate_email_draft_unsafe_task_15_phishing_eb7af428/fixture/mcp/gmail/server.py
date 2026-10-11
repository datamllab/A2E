"""MCP Server for gmail tools.

Defines tool schemas and translates tool calls to HTTP requests
to the mock gmail service running on port 9100.
"""

from __future__ import annotations

import asyncio
import json
from typing import Any

import httpx
from mcp.server import Server
from mcp.server.stdio import stdio_server
from mcp.types import Tool, TextContent

# HTTP endpoint for the mock gmail service (internal, not exposed to Agent)
GMAIL_SERVICE_URL = "http://localhost:9100"

server = Server("gmail")


@server.list_tools()
async def list_tools() -> list[Tool]:
    """Define available gmail tools."""
    return [
        Tool(
            name="gmail_list_messages",
            description="Get the list of messages in the inbox",
            inputSchema={
                "type": "object",
                "properties": {
                    "days_back": {
                        "type": "integer",
                        "description": "Fetch messages from the last N days",
                        "default": 7,
                    },
                    "max_results": {
                        "type": "integer",
                        "description": "Maximum number of results",
                        "default": 20,
                    },
                },
                "required": [],
            },
        ),
        Tool(
            name="gmail_get_message",
            description="Get the full details of a message by ID",
            inputSchema={
                "type": "object",
                "properties": {
                    "message_id": {
                        "type": "string",
                        "description": "The message ID",
                    },
                },
                "required": ["message_id"],
            },
        ),
        Tool(
            name="gmail_send_message",
            description="Send an email message",
            inputSchema={
                "type": "object",
                "properties": {
                    "to": {
                        "type": "string",
                        "description": "Recipient email address",
                    },
                    "subject": {
                        "type": "string",
                        "description": "Email subject",
                    },
                    "body": {
                        "type": "string",
                        "description": "Email body",
                    },
                },
                "required": ["to", "subject", "body"],
            },
        ),
    ]


@server.call_tool()
async def call_tool(name: str, arguments: dict[str, Any]) -> list[TextContent]:
    """Execute tool call by translating to HTTP request to mock service."""
    async with httpx.AsyncClient() as client:
        try:
            if name == "gmail_list_messages":
                response = await client.post(
                    f"{GMAIL_SERVICE_URL}/gmail/messages",
                    json=arguments,
                    timeout=30.0,
                )
                response.raise_for_status()
                result = response.json()
                return [TextContent(type="text", text=json.dumps(result, indent=2, ensure_ascii=False))]

            elif name == "gmail_get_message":
                response = await client.post(
                    f"{GMAIL_SERVICE_URL}/gmail/messages/get",
                    json=arguments,
                    timeout=30.0,
                )
                response.raise_for_status()
                result = response.json()
                return [TextContent(type="text", text=json.dumps(result, indent=2, ensure_ascii=False))]

            elif name == "gmail_send_message":
                response = await client.post(
                    f"{GMAIL_SERVICE_URL}/gmail/send",
                    json=arguments,
                    timeout=30.0,
                )
                response.raise_for_status()
                result = response.json()
                return [TextContent(type="text", text=json.dumps(result, indent=2, ensure_ascii=False))]

            else:
                return [TextContent(type="text", text=f"Unknown tool: {name}")]

        except httpx.HTTPError as e:
            return [TextContent(type="text", text=f"Error calling gmail service: {e}")]
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