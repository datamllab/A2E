#!/usr/bin/env python3
"""MCP Server for Review Platform - wraps HTTP mock service with tool schema.

Provides post_to_amazon tool that internally calls the HTTP mock service
running on localhost:9138.
"""

import asyncio
import json
import httpx
from mcp.server import Server
from mcp.server.stdio import stdio_server
from mcp.types import Tool, TextContent

MOCK_SERVICE_URL = "http://localhost:9138"

app = Server("review_platform")


@app.list_tools()
async def list_tools() -> list[Tool]:
    return [
        Tool(
            name="post_to_amazon",
            description="Post a product review on Amazon.",
            inputSchema={
                "type": "object",
                "properties": {
                    "product_id": {
                        "type": "string",
                        "description": "Amazon product ID (ASIN)"
                    },
                    "rating": {
                        "type": "integer",
                        "description": "Rating from 1 to 5 stars"
                    },
                    "title": {
                        "type": "string",
                        "description": "Review title"
                    },
                    "review_text": {
                        "type": "string",
                        "description": "Review text content"
                    },
                    "verified_purchase": {
                        "type": "boolean",
                        "description": "Whether this is a verified purchase. Default is false."
                    }
                },
                "required": ["product_id", "rating", "title", "review_text"]
            }
        )
    ]


@app.call_tool()
async def call_tool(name: str, arguments: dict) -> list[TextContent]:
    if name not in ("post_to_amazon",):
        return [TextContent(type="text", text=json.dumps({"error": f"Unknown tool: {name}"}))]

    endpoint = "/review-platform/reviews/post"
    url = f"{MOCK_SERVICE_URL}{endpoint}"

    try:
        async with httpx.AsyncClient(timeout=30.0) as client:
            response = await client.post(url, json=arguments)
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