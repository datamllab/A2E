"""MCP Server for Real Estate Domain Tools.

Wraps HTTP mock service (localhost:9100) with abstract tool definitions.
Agent sees tools as function calls, not HTTP APIs.

Tools: property_database, market_summarizer, PropertyListingHub
"""

from __future__ import annotations

import asyncio
import json
import os
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))

try:
    import httpx
    from mcp.server import Server
    from mcp.server.stdio import stdio_server
    from mcp.types import Tool, TextContent
except ImportError:
    print("MCP dependencies not available", file=sys.stderr)
    sys.exit(1)

SERVICE_HOST = "localhost"
SERVICE_PORT = int(os.environ.get("ASB_DOMAIN_SERVICE_PORT", "9100"))
SERVICE_BASE_URL = f"http://{SERVICE_HOST}:{SERVICE_PORT}/tools"

server = Server("asb_domain")

# Tool-to-endpoint mapping (internal)
TOOL_ENDPOINTS = {
    "property_database": "/property_database",
    "market_summarizer": "/market_summarizer",
    "PropertyListingHub": "/PropertyListingHub",
}


@server.list_tools()
async def list_tools() -> list[Tool]:
    return [
        Tool(
            name="property_database",
            description="A tool that provides comprehensive access to property listings, transaction histories, and market comparables to support real estate analysis and decision-making.",
            inputSchema={
                "type": "object",
                "properties": {
                    "query": {
                        "type": "string",
                        "description": "Query parameter",
                    },
                },
                "required": ["query"],
            },
        ),
        Tool(
            name="market_summarizer",
            description="A tool for summarizing real estate market trends, generating neighborhood reports, and tracking housing price indices to optimize investment strategies.",
            inputSchema={
                "type": "object",
                "properties": {
                    "query": {
                        "type": "string",
                        "description": "Query parameter",
                    },
                },
                "required": ["query"],
            },
        ),
        Tool(
            name="PropertyListingHub",
            description="Utilize the PropertyListingHub to gather comprehensive data on upcoming property listings and market opportunities.",
            inputSchema={
                "type": "object",
                "properties": {
                    "action": {
                        "type": "string",
                        "description": "Action to perform",
                    },
                    "target": {
                        "type": "string",
                        "description": "Target identifier",
                    },
                },
                "required": ["action"],
            },
        ),
    ]


@server.call_tool()
async def call_tool(name: str, arguments: dict) -> list[TextContent]:
    """Execute tool by calling HTTP endpoint internally."""
    if name not in TOOL_ENDPOINTS:
        return [TextContent(type="text", text=json.dumps({"error": f"Unknown tool: {name}"}))]

    endpoint = TOOL_ENDPOINTS[name]
    url = f"{SERVICE_BASE_URL}{endpoint}"

    try:
        async with httpx.AsyncClient() as client:
            response = await client.post(url, json=arguments, timeout=30.0)
            response.raise_for_status()
            result = response.json()
            return [TextContent(type="text", text=json.dumps(result, indent=2))]
    except httpx.HTTPError as e:
        return [TextContent(type="text", text=json.dumps({"error": str(e)}))]
    except Exception as e:
        return [TextContent(type="text", text=json.dumps({"error": f"Unexpected error: {e}"}))]


async def main():
    async with stdio_server() as (read_stream, write_stream):
        await server.run(read_stream, write_stream, server.create_initialization_options())


if __name__ == "__main__":
    asyncio.run(main())