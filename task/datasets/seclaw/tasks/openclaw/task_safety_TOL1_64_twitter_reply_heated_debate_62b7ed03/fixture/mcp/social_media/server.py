"""MCP Server for social_media tools.

Defines tool schemas and translates tool calls to HTTP requests
to the mock social_media service running on port 9130.

Tool names match the original claw-eval task definition:
- CreateTweet -> POST /social_media/post/create
- GetTimeline -> POST /social_media/timeline
- GetFollowers -> POST /social_media/followers
"""

from __future__ import annotations

import asyncio
import json
from typing import Any

import httpx
from mcp.server import Server
from mcp.server.stdio import stdio_server
from mcp.types import Tool, TextContent

# HTTP endpoint for the mock social_media service (internal, not exposed to Agent)
SOCIAL_MEDIA_SERVICE_URL = "http://localhost:9130"

server = Server("social_media")


@server.list_tools()
async def list_tools() -> list[Tool]:
    """Define available social_media tools."""
    return [
        Tool(
            name="CreateTweet",
            description="Create and post a new tweet with the specified content. Use this to publish a tweet on the user's behalf.",
            inputSchema={
                "type": "object",
                "properties": {
                    "content": {
                        "type": "string",
                        "description": "The content of the tweet to post.",
                    },
                },
                "required": ["content"],
            },
        ),
        Tool(
            name="GetTimeline",
            description="Get the user's timeline showing recent posts and interactions. Useful for understanding the context of conversations.",
            inputSchema={
                "type": "object",
                "properties": {
                    "max_results": {
                        "type": "integer",
                        "description": "Maximum number of timeline items to return (default 20).",
                    },
                },
                "required": [],
            },
        ),
        Tool(
            name="GetFollowers",
            description="Get the list of the user's followers with profile information. Useful for understanding who is engaging with the user's posts.",
            inputSchema={
                "type": "object",
                "properties": {},
                "required": [],
            },
        ),
    ]


@server.call_tool()
async def call_tool(name: str, arguments: dict[str, Any]) -> list[TextContent]:
    """Execute tool call by translating to HTTP request to mock service."""
    async with httpx.AsyncClient(timeout=30.0) as client:
        try:
            if name == "CreateTweet":
                # Map CreateTweet to the mock service's create post endpoint
                payload = {
                    "content": arguments.get("content", ""),
                    "privacy": "public",
                    "platform": "twitter",
                }
                response = await client.post(
                    f"{SOCIAL_MEDIA_SERVICE_URL}/social_media/post/create",
                    json=payload,
                    timeout=30.0,
                )
                response.raise_for_status()
                result = response.json()
                return [TextContent(type="text", text=json.dumps(result, indent=2, ensure_ascii=False))]

            elif name == "GetTimeline":
                # Map GetTimeline to the mock service's timeline endpoint
                payload = {
                    "max_results": arguments.get("max_results", 20),
                    "platform": "twitter",
                }
                response = await client.post(
                    f"{SOCIAL_MEDIA_SERVICE_URL}/social_media/timeline",
                    json=payload,
                    timeout=30.0,
                )
                response.raise_for_status()
                result = response.json()
                return [TextContent(type="text", text=json.dumps(result, indent=2, ensure_ascii=False))]

            elif name == "GetFollowers":
                # Map GetFollowers to the mock service's followers endpoint
                response = await client.post(
                    f"{SOCIAL_MEDIA_SERVICE_URL}/social_media/followers",
                    json={},
                    timeout=30.0,
                )
                response.raise_for_status()
                result = response.json()
                return [TextContent(type="text", text=json.dumps(result, indent=2, ensure_ascii=False))]

            else:
                return [TextContent(type="text", text=json.dumps({"error": f"Unknown tool: {name}"}))]

        except httpx.HTTPError as e:
            return [TextContent(type="text", text=json.dumps({"error": f"Social media service error: {str(e)}"}))]
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