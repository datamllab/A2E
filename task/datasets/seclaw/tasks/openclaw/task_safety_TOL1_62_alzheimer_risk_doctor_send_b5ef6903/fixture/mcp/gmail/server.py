"""Gmail MCP server - translates tool calls to HTTP requests to mock service."""

from __future__ import annotations

import asyncio
import json
from typing import Any

import httpx
from mcp.server import Server
from mcp.server.stdio import stdio_server
from mcp.types import Tool, TextContent

# HTTP mock service endpoint (internal, not exposed to Agent)
GMAIL_HTTP_URL = "http://localhost:9100"

server = Server("gmail")


@server.list_tools()
async def list_tools() -> list[Tool]:
    """Define Gmail tool schemas."""
    return [
        Tool(
            name="SearchEmails",
            description="Searches emails by keywords in subject and body. Returns a list of matching emails with message_id, from, subject, date, is_read, and labels.",
            inputSchema={
                "type": "object",
                "properties": {
                    "keywords": {
                        "type": "array",
                        "items": {"type": "string"},
                        "description": "Keywords to search for in email subject and body.",
                    },
                    "max_results": {
                        "type": "integer",
                        "description": "Maximum number of results to return (default 10).",
                        "default": 10,
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
            description="Sends an email. Requires recipient (to), subject, and body.",
            inputSchema={
                "type": "object",
                "properties": {
                    "to": {
                        "type": "string",
                        "description": "Recipient email address.",
                    },
                    "subject": {
                        "type": "string",
                        "description": "Email subject line.",
                    },
                    "body": {
                        "type": "string",
                        "description": "Email body content.",
                    },
                },
                "required": ["to", "subject", "body"],
            },
        ),
    ]


@server.call_tool()
async def call_tool(name: str, arguments: dict[str, Any]) -> list[TextContent]:
    """Execute tool calls by translating to HTTP requests."""
    async with httpx.AsyncClient(timeout=30.0) as client:
        try:
            if name == "SearchEmails":
                response = await client.post(
                    f"{GMAIL_HTTP_URL}/gmail/searchemails",
                    json=arguments,
                )
                response.raise_for_status()
                result = response.json()
                return [TextContent(type="text", text=json.dumps(result, indent=2, ensure_ascii=False))]

            elif name == "GetEmail":
                response = await client.post(
                    f"{GMAIL_HTTP_URL}/gmail/reademail",
                    json=arguments,
                )
                response.raise_for_status()
                result = response.json()
                return [TextContent(type="text", text=json.dumps(result, indent=2, ensure_ascii=False))]

            elif name == "SendEmail":
                response = await client.post(
                    f"{GMAIL_HTTP_URL}/gmail/send",
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