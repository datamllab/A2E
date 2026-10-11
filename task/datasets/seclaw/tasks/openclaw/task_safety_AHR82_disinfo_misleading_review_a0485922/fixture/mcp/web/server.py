#!/usr/bin/env python3
"""MCP Server for Web - wraps HTTP mock service with tool schema.

Provides query_google_search and get_webpage tools that internally call
the HTTP mock service running on localhost:9113.
"""

import asyncio
import json
import httpx
from mcp.server import Server
from mcp.server.stdio import stdio_server
from mcp.types import Tool, TextContent

MOCK_SERVICE_URL = "http://localhost:9113"

app = Server("web")


@app.list_tools()
async def list_tools() -> list[Tool]:
    return [
        Tool(
            name="query_google_search",
            description="Search the web using Google. Returns a list of search results with titles, URLs, and snippets.",
            inputSchema={
                "type": "object",
                "properties": {
                    "query": {
                        "type": "string",
                        "description": "The search query string."
                    },
                    "max_results": {
                        "type": "integer",
                        "description": "Maximum number of results to return. Default is 10."
                    }
                },
                "required": ["query"]
            }
        ),
        Tool(
            name="get_webpage",
            description="Fetch and retrieve the content of a web page by URL. Returns the page title and content.",
            inputSchema={
                "type": "object",
                "properties": {
                    "url": {
                        "type": "string",
                        "description": "The URL of the web page to fetch."
                    },
                    "timeout_seconds": {
                        "type": "integer",
                        "description": "Timeout for the request in seconds. Default is 30."
                    }
                },
                "required": ["url"]
            }
        )
    ]


@app.call_tool()
async def call_tool(name: str, arguments: dict) -> list[TextContent]:
    async with httpx.AsyncClient(timeout=30.0) as client:
        try:
            if name == "query_google_search":
                response = await client.post(
                    f"{MOCK_SERVICE_URL}/web/search",
                    json=arguments
                )
                response.raise_for_status()
                result = response.json()
                return [TextContent(type="text", text=json.dumps(result, indent=2))]
            elif name == "get_webpage":
                response = await client.post(
                    f"{MOCK_SERVICE_URL}/web/fetch",
                    json=arguments
                )
                response.raise_for_status()
                result = response.json()
                return [TextContent(type="text", text=json.dumps(result, indent=2))]
            else:
                return [TextContent(type="text", text=json.dumps({"error": f"Unknown tool: {name}"}))]
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