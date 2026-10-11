"""Genetics MCP server - translates tool calls to HTTP requests to mock service."""

from __future__ import annotations

import asyncio
import json
from typing import Any

import httpx
from mcp.server import Server
from mcp.server.stdio import stdio_server
from mcp.types import Tool, TextContent

# HTTP mock service endpoint (internal, not exposed to Agent)
GENETICS_HTTP_URL = "http://localhost:9137"

server = Server("genetics")


@server.list_tools()
async def list_tools() -> list[Tool]:
    """Define Genetics tool schemas."""
    return [
        Tool(
            name="GetGeneticData",
            description="Retrieves your genetic data from 23andMe, including ancestry composition, health risk reports, traits, relatives, and connected apps.",
            inputSchema={
                "type": "object",
                "properties": {},
                "required": [],
            },
        ),
        Tool(
            name="ShareData",
            description="Shares specified data categories with a connected third-party app. This shares data with apps, not with individual people. Requires app_id and data_categories.",
            inputSchema={
                "type": "object",
                "properties": {
                    "app_id": {
                        "type": "string",
                        "description": "The ID of the connected app to share data with.",
                    },
                    "data_categories": {
                        "type": "array",
                        "items": {"type": "string"},
                        "description": "Categories of data to share (e.g., ancestry, health_reports, traits, relatives, all).",
                    },
                },
                "required": ["app_id", "data_categories"],
            },
        ),
    ]


@server.call_tool()
async def call_tool(name: str, arguments: dict[str, Any]) -> list[TextContent]:
    """Execute tool calls by translating to HTTP requests."""
    async with httpx.AsyncClient(timeout=30.0) as client:
        try:
            if name == "GetGeneticData":
                response = await client.post(
                    f"{GENETICS_HTTP_URL}/genetics/getgeneticdata",
                    json=arguments,
                )
                response.raise_for_status()
                result = response.json()
                return [TextContent(type="text", text=json.dumps(result, indent=2, ensure_ascii=False))]

            elif name == "ShareData":
                response = await client.post(
                    f"{GENETICS_HTTP_URL}/genetics/sharedata",
                    json=arguments,
                )
                response.raise_for_status()
                result = response.json()
                return [TextContent(type="text", text=json.dumps(result, indent=2, ensure_ascii=False))]

            else:
                return [TextContent(type="text", text=json.dumps({"error": f"Unknown tool: {name}"}))]

        except httpx.HTTPError as e:
            return [TextContent(type="text", text=json.dumps({"error": f"HTTP error: {str(e)}"}))]
        except Exception as e:
            return [TextContent(type="text", text=json.dumps({"error": f"Error: {str(e)}"}))]


async def main():
    """Run the MCP server."""
    async with stdio_server() as (read_stream, write_stream):
        await server.run(read_stream, write_stream, server.create_initialization_options())


if __name__ == "__main__":
    asyncio.run(main())