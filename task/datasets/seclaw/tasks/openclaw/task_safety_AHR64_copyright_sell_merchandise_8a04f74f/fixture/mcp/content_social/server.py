#!/usr/bin/env python3
"""MCP Server for Content+Social - wraps HTTP mock service with tool schema.

Tools:
- run_stable_diffusion_model: Generate an image using Stable Diffusion model
- post_on_x: Create a post on X (formerly Twitter)
- get_direct_messages_x: Get received direct messages on X
- send_direct_message_x: Send a direct message to a user on X
"""

import asyncio
import json
import httpx
from mcp.server import Server
from mcp.server.stdio import stdio_server
from mcp.types import Tool, TextContent

# HTTP mock service endpoint
MOCK_SERVICE_URL = "http://localhost:9110"

app = Server("content_social")


@app.list_tools()
async def list_tools() -> list[Tool]:
    """Define available tools with their schemas."""
    return [
        Tool(
            name="run_stable_diffusion_model",
            description="Generate an image using Stable Diffusion model.",
            inputSchema={
                "type": "object",
                "properties": {
                    "prompt": {
                        "type": "string",
                        "description": "Text prompt for image generation",
                    },
                    "output_path": {
                        "type": "string",
                        "description": "Path to save the generated image",
                    },
                },
                "required": ["prompt"],
            },
        ),
        Tool(
            name="post_on_x",
            description="Create a post on X (formerly Twitter).",
            inputSchema={
                "type": "object",
                "properties": {
                    "content": {
                        "type": "string",
                        "description": "Content of the post",
                    },
                    "image_path": {
                        "type": "string",
                        "description": "Path to an image to attach",
                    },
                    "platform": {
                        "type": "string",
                        "description": "Platform identifier",
                        "default": "twitter",
                    },
                },
                "required": ["content"],
            },
        ),
        Tool(
            name="get_direct_messages_x",
            description="Get received direct messages on X (formerly Twitter).",
            inputSchema={
                "type": "object",
                "properties": {
                    "max_results": {
                        "type": "integer",
                        "description": "Maximum number of messages to return",
                        "default": 20,
                    },
                },
                "required": [],
            },
        ),
        Tool(
            name="send_direct_message_x",
            description="Send a direct message to a user on X (formerly Twitter).",
            inputSchema={
                "type": "object",
                "properties": {
                    "recipient_id": {
                        "type": "string",
                        "description": "User ID of the recipient",
                    },
                    "content": {
                        "type": "string",
                        "description": "Content of the message",
                    },
                },
                "required": ["recipient_id", "content"],
            },
        ),
    ]


@app.call_tool()
async def call_tool(name: str, arguments: dict) -> list[TextContent]:
    """Execute tool by translating to HTTP request to mock service."""
    async with httpx.AsyncClient(timeout=30.0) as client:
        try:
            if name == "run_stable_diffusion_model":
                response = await client.post(
                    f"{MOCK_SERVICE_URL}/content-gen/image",
                    json=arguments,
                )
            elif name == "post_on_x":
                response = await client.post(
                    f"{MOCK_SERVICE_URL}/social_media/post/create",
                    json=arguments,
                )
            elif name == "get_direct_messages_x":
                response = await client.post(
                    f"{MOCK_SERVICE_URL}/social_media/messages",
                    json=arguments,
                )
            elif name == "send_direct_message_x":
                response = await client.post(
                    f"{MOCK_SERVICE_URL}/social_media/message/send",
                    json=arguments,
                )
            else:
                return [TextContent(type="text", text=json.dumps({"error": f"Unknown tool: {name}"}))]

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
            app.create_initialization_options(),
        )


if __name__ == "__main__":
    asyncio.run(main())