#!/usr/bin/env python3
"""MCP Server for Social Media - wraps HTTP mock service with tool schema.

Exposes social media tools (CreateTweet, GetTimeline, SendMessage) to the agent
via MCP protocol, translating calls to HTTP requests to the internal mock service.
"""

import asyncio
import json
import httpx
from mcp.server import Server
from mcp.server.stdio import stdio_server
from mcp.types import Tool, TextContent

# HTTP mock service endpoint (internal, not exposed to Agent)
MOCK_SERVICE_URL = "http://localhost:9138"

app = Server("social_media")


@app.list_tools()
async def list_tools() -> list[Tool]:
    """Define available tools with their schemas."""
    return [
        Tool(
            name="CreateTweet",
            description="Create and publish a tweet on the user's social media account.",
            inputSchema={
                "type": "object",
                "properties": {
                    "content": {
                        "type": "string",
                        "description": "The content of the tweet"
                    }
                },
                "required": ["content"]
            }
        ),
        Tool(
            name="GetTimeline",
            description="Get the user's social media timeline.",
            inputSchema={
                "type": "object",
                "properties": {}
            }
        ),
        Tool(
            name="SendMessage",
            description="Send a direct message to another user.",
            inputSchema={
                "type": "object",
                "properties": {
                    "recipient_id": {
                        "type": "string",
                        "description": "The user ID of the message recipient"
                    },
                    "content": {
                        "type": "string",
                        "description": "The content of the message"
                    }
                },
                "required": ["recipient_id", "content"]
            }
        )
    ]


# Map tool names to HTTP endpoints
_TOOL_ROUTES = {
    "CreateTweet": "/social_media/createtweet",
    "GetTimeline": "/social_media/gettimeline",
    "SendMessage": "/social_media/sendmessage",
}


@app.call_tool()
async def call_tool(name: str, arguments: dict) -> list[TextContent]:
    """Execute tool by translating to HTTP request to mock service."""
    route = _TOOL_ROUTES.get(name)
    if not route:
        return [TextContent(type="text", text=json.dumps({"error": f"Unknown tool: {name}"}))]

    # Remove None/empty arguments
    filtered_args = {k: v for k, v in arguments.items() if v is not None and v != ""}

    async with httpx.AsyncClient(timeout=30.0) as client:
        try:
            response = await client.post(
                f"{MOCK_SERVICE_URL}{route}",
                json=filtered_args
            )
            response.raise_for_status()
            result = response.json()
            return [TextContent(type="text", text=json.dumps(result, indent=2))]

        except httpx.HTTPError as e:
            return [TextContent(type="text", text=json.dumps({"error": f"HTTP error: {str(e)}"}))]
        except Exception as e:
            return [TextContent(type="text", text=json.dumps({"error": f"Error: {str(e)}"}))]


async def main():
    async with stdio_server() as (read_stream, write_stream):
        await app.run(
            read_stream,
            write_stream,
            app.create_initialization_options()
        )


if __name__ == "__main__":
    asyncio.run(main())