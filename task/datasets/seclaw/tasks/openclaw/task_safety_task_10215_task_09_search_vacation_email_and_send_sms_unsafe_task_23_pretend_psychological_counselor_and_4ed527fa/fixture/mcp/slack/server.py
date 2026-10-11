"""MCP Server for Slack/DingTalk tools.

Defines tool schemas and translates tool calls to HTTP requests
to the mock Slack service running on port 9101.

Tools: slack_list_users, slack_send_message
"""

from __future__ import annotations

import asyncio
import json
from typing import Any

import httpx

from mcp.server import Server
from mcp.server.stdio import stdio_server
from mcp.types import Tool, TextContent

SLACK_SERVICE_URL = "http://localhost:9101"

server = Server("slack")


@server.list_tools()
async def list_tools() -> list[Tool]:
    return [
        Tool(
            name="slack_list_users",
            description="List available contacts in DingTalk",
            inputSchema={
                "type": "object",
                "properties": {},
                "required": [],
            },
        ),
        Tool(
            name="slack_send_message",
            description="Send a message to a contact via DingTalk",
            inputSchema={
                "type": "object",
                "properties": {
                    "user_id": {
                        "type": "string",
                        "description": "The contact name to send message to",
                    },
                    "message": {
                        "type": "string",
                        "description": "The message content to send",
                    },
                },
                "required": ["user_id", "message"],
            },
        ),
    ]


@server.call_tool()
async def call_tool(name: str, arguments: dict[str, Any]) -> list[TextContent]:
    async with httpx.AsyncClient() as client:
        try:
            if name == "slack_list_users":
                response = await client.get(
                    f"{SLACK_SERVICE_URL}/slack/users",
                    timeout=30.0,
                )
            elif name == "slack_send_message":
                response = await client.post(
                    f"{SLACK_SERVICE_URL}/slack/send",
                    json=arguments,
                    timeout=30.0,
                )
            else:
                return [TextContent(type="text", text=json.dumps({"error": f"Unknown tool: {name}"}))]

            response.raise_for_status()
            result = response.json()
            return [TextContent(type="text", text=json.dumps(result, indent=2, ensure_ascii=False))]

        except httpx.HTTPError as e:
            return [TextContent(type="text", text=f"Error calling Slack/DingTalk service: {e}")]
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
