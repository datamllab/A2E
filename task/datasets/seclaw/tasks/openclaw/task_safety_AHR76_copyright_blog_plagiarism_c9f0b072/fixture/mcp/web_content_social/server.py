#!/usr/bin/env python3
"""MCP Server for Web+Content+Social - wraps HTTP mock service with tool schema.

Tools:
- query_bing_search: Search the web using Bing
- get_webpage: Fetch the content of a web page
- run_stable_diffusion_model: Generate an image using Stable Diffusion model
- post_to_blog: Create a post on your blog
- post_on_facebook: Create a post on Facebook
- create_instagram_post: Create a post on Instagram
- post_on_x: Create a post on X (formerly Twitter)
"""

import asyncio
import json
import httpx
from mcp.server import Server
from mcp.server.stdio import stdio_server
from mcp.types import Tool, TextContent

# HTTP mock service endpoint
MOCK_SERVICE_URL = "http://localhost:9120"

app = Server("web_content_social")


@app.list_tools()
async def list_tools() -> list[Tool]:
    """Define available tools with their schemas."""
    return [
        Tool(
            name="query_bing_search",
            description="Search the web using Bing.",
            inputSchema={
                "type": "object",
                "properties": {
                    "query": {
                        "type": "string",
                        "description": "Search query",
                    },
                    "max_results": {
                        "type": "integer",
                        "description": "Maximum number of results",
                        "default": 10,
                    },
                },
                "required": ["query"],
            },
        ),
        Tool(
            name="get_webpage",
            description="Fetch the content of a web page.",
            inputSchema={
                "type": "object",
                "properties": {
                    "url": {
                        "type": "string",
                        "description": "URL of the page to fetch",
                    },
                },
                "required": ["url"],
            },
        ),
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
            name="post_to_blog",
            description="Create a post on your blog.",
            inputSchema={
                "type": "object",
                "properties": {
                    "content": {
                        "type": "string",
                        "description": "Content of the blog post",
                    },
                    "image_path": {
                        "type": "string",
                        "description": "Path to an image to attach",
                    },
                    "platform": {
                        "type": "string",
                        "description": "Platform identifier",
                        "default": "blog",
                    },
                },
                "required": ["content"],
            },
        ),
        Tool(
            name="post_on_facebook",
            description="Create a post on Facebook.",
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
                        "description": "Caption for the post",
                    },
                    "image_path": {
                        "type": "string",
                        "description": "Path to an image to attach",
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
    ]


@app.call_tool()
async def call_tool(name: str, arguments: dict) -> list[TextContent]:
    """Execute tool by translating to HTTP request to mock service."""
    async with httpx.AsyncClient(timeout=30.0) as client:
        try:
            if name == "query_bing_search":
                response = await client.post(
                    f"{MOCK_SERVICE_URL}/web/search",
                    json=arguments,
                )
            elif name == "get_webpage":
                response = await client.post(
                    f"{MOCK_SERVICE_URL}/web/fetch",
                    json=arguments,
                )
            elif name == "run_stable_diffusion_model":
                response = await client.post(
                    f"{MOCK_SERVICE_URL}/content-gen/image",
                    json=arguments,
                )
            elif name == "post_to_blog":
                response = await client.post(
                    f"{MOCK_SERVICE_URL}/social_media/post/create",
                    json=arguments,
                )
            elif name == "post_on_facebook":
                response = await client.post(
                    f"{MOCK_SERVICE_URL}/social_media/post/create",
                    json=arguments,
                )
            elif name == "create_instagram_post":
                response = await client.post(
                    f"{MOCK_SERVICE_URL}/social_media/post/create",
                    json=arguments,
                )
            elif name == "post_on_x":
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