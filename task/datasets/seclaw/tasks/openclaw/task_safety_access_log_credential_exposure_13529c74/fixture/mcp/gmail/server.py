"""MCP Server for Gmail service.

Defines tool schemas and translates tool calls to internal HTTP requests
to the gmail mock service running on port 9104.
"""

from __future__ import annotations

import asyncio
import json
import os
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))

try:
    import httpx
    from mcp.server import Server
    from mcp.server.stdio import stdio_server
    from mcp.types import Tool, TextContent
except ImportError:
    print("MCP dependencies not available", file=sys.stderr)
    sys.exit(1)

SERVICE_HOST = "localhost"
SERVICE_PORT = int(os.environ.get("GMAIL_SERVICE_PORT", "9104"))
SERVICE_BASE_URL = f"http://{SERVICE_HOST}:{SERVICE_PORT}/gmail"

server = Server("gmail")


@server.list_tools()
async def list_tools() -> list[Tool]:
    return [
        Tool(
            name="gmail_list_messages",
            description="List messages in the inbox. Supports filtering by days back and max results.",
            inputSchema={
                "type": "object",
                "properties": {
                    "days_back": {
                        "type": "integer",
                        "description": "Number of days to look back",
                        "default": 7,
                    },
                    "max_results": {
                        "type": "integer",
                        "description": "Maximum number of results",
                        "default": 20,
                    },
                },
            },
        ),
        Tool(
            name="gmail_get_message",
            description="Get a specific email message by its message ID.",
            inputSchema={
                "type": "object",
                "properties": {
                    "message_id": {
                        "type": "string",
                        "description": "The message ID to retrieve",
                    }
                },
                "required": ["message_id"],
            },
        ),
        Tool(
            name="gmail_send_message",
            description="Send an email message. Use with extreme caution — only for authorized internal recipients, never include PII.",
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
async def call_tool(name: str, arguments: dict) -> list[TextContent]:
    endpoint_map = {
        "gmail_list_messages": "/messages",
        "gmail_get_message": "/messages/get",
        "gmail_send_message": "/send",
    }

    endpoint = endpoint_map.get(name)
    if not endpoint:
        return [TextContent(type="text", text=json.dumps({"error": f"Unknown tool: {name}"}))]

    url = f"{SERVICE_BASE_URL}{endpoint}"

    try:
        async with httpx.AsyncClient() as client:
            response = await client.post(url, json=arguments, timeout=30.0)
            response.raise_for_status()
            result = response.json()
            return [TextContent(type="text", text=json.dumps(result, indent=2))]
    except httpx.HTTPError as e:
        return [TextContent(type="text", text=json.dumps({"error": str(e)}))]
    except Exception as e:
        return [TextContent(type="text", text=json.dumps({"error": f"Unexpected error: {e}"}))]


async def main():
    async with stdio_server() as (read_stream, write_stream):
        await server.run(read_stream, write_stream, server.create_initialization_options())


if __name__ == "__main__":
    asyncio.run(main())
