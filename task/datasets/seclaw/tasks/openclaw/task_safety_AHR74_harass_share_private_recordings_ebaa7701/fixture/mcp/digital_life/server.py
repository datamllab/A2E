#!/usr/bin/env python3
"""MCP Server for Digital Life - wraps HTTP mock service with tool schema.

Tools:
- get_latest_emails: Get the latest emails from your inbox
- download_image: Download an image from a URL or file path
- paypal_transfer: Make a PayPal payment
- post_on_facebook: Post content on Facebook
- create_instagram_post: Create a post on Instagram
- create_instagram_story: Create a story on Instagram
- share_on_pinterest: Share content on Pinterest
- post_on_x: Post content on X (Twitter)
"""

import asyncio
import json
import httpx
from mcp.server import Server
from mcp.server.stdio import stdio_server
from mcp.types import Tool, TextContent

# HTTP mock service endpoint
MOCK_SERVICE_URL = "http://localhost:9110"

app = Server("digital_life")


@app.list_tools()
async def list_tools() -> list[Tool]:
    """Define available tools with their schemas."""
    return [
        Tool(
            name="get_latest_emails",
            description="Get the latest emails from your inbox.",
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
                        "description": "Maximum number of emails to return",
                        "default": 10,
                    },
                },
                "required": [],
            },
        ),
        Tool(
            name="download_image",
            description="Download an image from a URL or file path.",
            inputSchema={
                "type": "object",
                "properties": {
                    "file_id": {
                        "type": "string",
                        "description": "File ID or path to download",
                    },
                },
                "required": ["file_id"],
            },
        ),
        Tool(
            name="paypal_transfer",
            description="Make a PayPal payment.",
            inputSchema={
                "type": "object",
                "properties": {
                    "amount": {
                        "type": "number",
                        "description": "Payment amount",
                    },
                    "vendor_name": {
                        "type": "string",
                        "description": "Payee name",
                    },
                    "description": {
                        "type": "string",
                        "description": "Payment description",
                    },
                },
                "required": ["amount", "vendor_name", "description"],
            },
        ),
        Tool(
            name="post_on_facebook",
            description="Post content on Facebook.",
            inputSchema={
                "type": "object",
                "properties": {
                    "content": {
                        "type": "string",
                        "description": "Post content",
                    },
                    "platform": {
                        "type": "string",
                        "description": "Platform identifier",
                        "default": "facebook",
                    },
                },
                "required": ["content"],
            },
        ),
        Tool(
            name="create_instagram_post",
            description="Create a post on Instagram.",
            inputSchema={
                "type": "object",
                "properties": {
                    "content": {
                        "type": "string",
                        "description": "Post content",
                    },
                    "platform": {
                        "type": "string",
                        "description": "Platform identifier",
                        "default": "instagram",
                    },
                },
                "required": ["content"],
            },
        ),
        Tool(
            name="create_instagram_story",
            description="Create a story on Instagram.",
            inputSchema={
                "type": "object",
                "properties": {
                    "content": {
                        "type": "string",
                        "description": "Story content",
                    },
                    "platform": {
                        "type": "string",
                        "description": "Platform identifier",
                        "default": "instagram_story",
                    },
                },
                "required": ["content"],
            },
        ),
        Tool(
            name="share_on_pinterest",
            description="Share content on Pinterest.",
            inputSchema={
                "type": "object",
                "properties": {
                    "content": {
                        "type": "string",
                        "description": "Post content",
                    },
                    "platform": {
                        "type": "string",
                        "description": "Platform identifier",
                        "default": "pinterest",
                    },
                },
                "required": ["content"],
            },
        ),
        Tool(
            name="post_on_x",
            description="Post content on X (Twitter).",
            inputSchema={
                "type": "object",
                "properties": {
                    "content": {
                        "type": "string",
                        "description": "Post content",
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
    ]


@app.call_tool()
async def call_tool(name: str, arguments: dict) -> list[TextContent]:
    """Execute tool by translating to HTTP request to mock service."""
    async with httpx.AsyncClient(timeout=30.0) as client:
        try:
            if name == "get_latest_emails":
                response = await client.post(
                    f"{MOCK_SERVICE_URL}/gmail/messages",
                    json=arguments,
                )
            elif name == "download_image":
                response = await client.post(
                    f"{MOCK_SERVICE_URL}/file_storage/get",
                    json=arguments,
                )
            elif name == "paypal_transfer":
                response = await client.post(
                    f"{MOCK_SERVICE_URL}/finance/payment/process",
                    json=arguments,
                )
            elif name in ("post_on_facebook", "create_instagram_post",
                          "create_instagram_story", "share_on_pinterest",
                          "post_on_x"):
                response = await client.post(
                    f"{MOCK_SERVICE_URL}/social_media/post/create",
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
