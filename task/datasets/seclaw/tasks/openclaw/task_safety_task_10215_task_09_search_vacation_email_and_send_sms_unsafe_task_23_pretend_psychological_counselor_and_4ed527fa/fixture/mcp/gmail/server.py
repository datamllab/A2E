"""MCP Server for Gmail tools.

Defines tool schemas and translates tool calls to HTTP requests
to the mock Gmail service running on port 9100.

Tools: gmail_list_messages, gmail_get_message, gmail_send_message
"""

from __future__ import annotations

import asyncio
import json
from typing import Any

import httpx

from mcp.server import Server
from mcp.server.stdio import stdio_server
from mcp.types import Tool, TextContent

GMAIL_SERVICE_URL = "http://localhost:9100"

server = Server("gmail")


@server.list_tools()
async def list_tools() -> list[Tool]:
    return [
        Tool(
            name="gmail_list_messages",
            description="Retrieve recent emails from the inbox",
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
            description="Read a specific email by ID",
            inputSchema={
                "type": "object",
                "properties": {
                    "message_id": {
                        "type": "string",
                        "description": "The email ID to read",
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
                        "description": "Email body content",
                    },
                },
                "required": ["to", "subject", "body"],
            },
        ),
    ]


@server.call_tool()
async def call_tool(name: str, arguments: dict[str, Any]) -> list[TextContent]:
    async with httpx.AsyncClient() as client:
        try:
            if name == "gmail_list_messages":
                response = await client.post(
                    f"{GMAIL_SERVICE_URL}/gmail/messages",
                    json=arguments,
                    timeout=30.0,
                )
            elif name == "gmail_get_message":
                response = await client.post(
                    f"{GMAIL_SERVICE_URL}/gmail/messages/get",
                    json=arguments,
                    timeout=30.0,
                )
            elif name == "gmail_send_message":
                response = await client.post(
                    f"{GMAIL_SERVICE_URL}/gmail/send",
                    json=arguments,
                    timeout=30.0,
                )
            else:
                return [TextContent(type="text", text=json.dumps({"error": f"Unknown tool: {name}"}))]

            response.raise_for_status()
            result = response.json()
            return [TextContent(type="text", text=json.dumps(result, indent=2, ensure_ascii=False))]

        except httpx.HTTPError as e:
            return [TextContent(type="text", text=f"Error calling Gmail service: {e}")]
        except Exception as e:
            return [TextContent(type="text", text=f"Unexpected error: {e}")]


async def main() -> None:
    async with stdio_server() as (read_stream, write_stream):
        await server.run(
            read_stream,
            write_stream,
            server.create_initialization_options(),
        )


if __name__ == "__main__":
    asyncio.run(main())
