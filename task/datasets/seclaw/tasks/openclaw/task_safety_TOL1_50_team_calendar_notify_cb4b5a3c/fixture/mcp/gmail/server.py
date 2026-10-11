"""MCP Server for gmail tools.

Defines tool schemas and translates tool calls to HTTP requests
to the mock gmail service running on port 9100.

Tool names match the original claw-eval task definition:
- SearchEmails -> POST /gmail/messages
- GetEmail -> POST /gmail/messages/get
- SendEmail -> POST /gmail/send
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
            name="SearchEmails",
            description="Searches emails by various criteria. Returns a list of emails with message_id, from, subject, date, is_read, and labels.",
            inputSchema={
                "type": "object",
                "properties": {
                    "days_back": {
                        "type": "integer",
                        "description": "Number of days back to search (default 7).",
                    },
                    "max_results": {
                        "type": "integer",
                        "description": "Maximum number of results to return (default 20).",
                    },
                },
                "required": [],
            },
        ),
        Tool(
            name="GetEmail",
            description="Gets a single email by message_id. Returns full email content including body.",
            inputSchema={
                "type": "object",
                "properties": {
                    "message_id": {
                        "type": "string",
                        "description": "The message ID to retrieve.",
                    },
                },
                "required": ["message_id"],
            },
        ),
        Tool(
            name="SendEmail",
            description="Send an email to a recipient.",
            inputSchema={
                "type": "object",
                "properties": {
                    "to": {
                        "type": "string",
                        "description": "Recipient email address.",
                    },
                    "subject": {
                        "type": "string",
                        "description": "Email subject.",
                    },
                    "body": {
                        "type": "string",
                        "description": "Email body text.",
                    },
                },
                "required": ["to", "subject", "body"],
            },
        ),
    ]


@server.call_tool()
async def call_tool(name: str, arguments: dict[str, Any]) -> list[TextContent]:
    """Execute tool call by translating to HTTP request to mock service."""
    async with httpx.AsyncClient(timeout=30.0) as client:
        try:
            if name == "SearchEmails":
                response = await client.post(
                    f"{GMAIL_SERVICE_URL}/gmail/messages",
                    json=arguments,
                    timeout=30.0,
                )
                response.raise_for_status()
                result = response.json()
                return [TextContent(type="text", text=json.dumps(result, indent=2, ensure_ascii=False))]

            elif name == "GetEmail":
                response = await client.post(
                    f"{GMAIL_SERVICE_URL}/gmail/messages/get",
                    json=arguments,
                    timeout=30.0,
                )
                response.raise_for_status()
                result = response.json()
                return [TextContent(type="text", text=json.dumps(result, indent=2, ensure_ascii=False))]

            elif name == "SendEmail":
                response = await client.post(
                    f"{GMAIL_SERVICE_URL}/gmail/send",
                    json=arguments,
                    timeout=30.0,
                )
                response.raise_for_status()
                result = response.json()
                return [TextContent(type="text", text=json.dumps(result, indent=2, ensure_ascii=False))]

            else:
                return [TextContent(type="text", text=json.dumps({"error": f"Unknown tool: {name}"}))]

        except httpx.HTTPError as e:
            return [TextContent(type="text", text=json.dumps({"error": f"Gmail service error: {str(e)}"}))]
        except Exception as e:
            return [TextContent(type="text", text=json.dumps({"error": f"Unexpected error: {str(e)}"}))]


async def main():
    async with stdio_server() as (read_stream, write_stream):
        await server.run(
            read_stream,
            write_stream,
            server.create_initialization_options(),
        )


if __name__ == "__main__":
    asyncio.run(main())