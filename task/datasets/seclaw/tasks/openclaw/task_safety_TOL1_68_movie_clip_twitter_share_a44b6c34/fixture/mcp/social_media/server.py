"""MCP Server for social_media service.

Defines tool schemas for Twitter-like social media operations and translates
MCP tool calls to HTTP requests to the social_media mock service.
"""

import os
from mcp.server import Server
from mcp.server.stdio import stdio_server
from mcp.types import Tool
import httpx

# Mock service port (internal, not exposed to agent)
MOCK_PORT = os.environ.get("SOCIAL_MEDIA_MOCK_PORT", "9134")
MOCK_BASE_URL = f"http://localhost:{MOCK_PORT}/social_media"

server = Server("social_media")


@server.list_tools()
async def list_tools() -> list[Tool]:
    """Return tool definitions for social_media service."""
    return [
        Tool(
            name="CreateTweet",
            description="Post a new tweet on Twitter.",
            inputSchema={
                "type": "object",
                "properties": {
                    "content": {
                        "type": "string",
                        "description": "Text content of the tweet",
                    },
                },
                "required": ["content"],
            },
        ),
        Tool(
            name="GetTimeline",
            description="Get the current user's Twitter timeline.",
            inputSchema={
                "type": "object",
                "properties": {},
                "required": [],
            },
        ),
        Tool(
            name="SendMessage",
            description="Send a direct message to another Twitter user.",
            inputSchema={
                "type": "object",
                "properties": {
                    "recipient_id": {
                        "type": "string",
                        "description": "User ID of the message recipient",
                    },
                    "content": {
                        "type": "string",
                        "description": "Text content of the message",
                    },
                },
                "required": ["recipient_id", "content"],
            },
        ),
    ]


@server.call_tool()
async def call_tool(name: str, arguments: dict) -> list:
    """Translate MCP tool calls to HTTP requests to the mock service."""
    async with httpx.AsyncClient(timeout=30.0) as client:
        url = f"{MOCK_BASE_URL}/{name.lower()}"
        response = await client.post(url, json=arguments)
        return [response.json()]


async def main():
    """Run the MCP server."""
    async with stdio_server() as (read_stream, write_stream):
        await server.run(read_stream, write_stream, server.create_initialization_options())


if __name__ == "__main__":
    import asyncio
    asyncio.run(main())