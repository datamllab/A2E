"""MCP Server for social_media tools.

Defines tool schemas and translates tool calls to HTTP requests
to the mock social_media service running on port 9130.
"""

from __future__ import annotations

import asyncio
import json
from typing import Any

import httpx
from mcp.server import Server
from mcp.server.stdio import stdio_server
from mcp.types import Tool, TextContent

SOCIAL_MEDIA_SERVICE_URL = "http://localhost:9130"

server = Server("social_media")


@server.list_tools()
async def list_tools() -> list[Tool]:
    return [
        Tool(
            name="CreateTweet",
            description="Post a tweet on Twitter.",
            inputSchema={
                "type": "object",
                "properties": {
                    "content": {
                        "type": "string",
                        "description": "The content of the tweet.",
                    },
                },
                "required": ["content"],
            },
        ),
        Tool(
            name="GetTimeline",
            description="Get the user's Twitter timeline.",
            inputSchema={
                "type": "object",
                "properties": {},
                "required": [],
            },
        ),
        Tool(
            name="SendMessage",
            description="Send a direct message to another user on Twitter.",
            inputSchema={
                "type": "object",
                "properties": {
                    "recipient_id": {
                        "type": "string",
                        "description": "The user ID of the message recipient.",
                    },
                    "content": {
                        "type": "string",
                        "description": "The content of the message.",
                    },
                },
                "required": ["recipient_id", "content"],
            },
        ),
    ]


@server.call_tool()
async def call_tool(name: str, arguments: dict[str, Any]) -> list[TextContent]:
    async with httpx.AsyncClient() as client:
        try:
            if name == "CreateTweet":
                response = await client.post(
                    f"{SOCIAL_MEDIA_SERVICE_URL}/social_media/createtweet",
                    json=arguments,
                    timeout=30.0,
                )
            elif name == "GetTimeline":
                response = await client.post(
                    f"{SOCIAL_MEDIA_SERVICE_URL}/social_media/gettimeline",
                    json=arguments,
                    timeout=30.0,
                )
            elif name == "SendMessage":
                response = await client.post(
                    f"{SOCIAL_MEDIA_SERVICE_URL}/social_media/sendmessage",
                    json=arguments,
                    timeout=30.0,
                )
            else:
                return [TextContent(type="text", text=f"Unknown tool: {name}")]

            response.raise_for_status()
            result = response.json()
            return [TextContent(type="text", text=json.dumps(result, indent=2, ensure_ascii=False))]

        except httpx.HTTPError as e:
            return [TextContent(type="text", text=f"Error calling social_media service: {e}")]
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