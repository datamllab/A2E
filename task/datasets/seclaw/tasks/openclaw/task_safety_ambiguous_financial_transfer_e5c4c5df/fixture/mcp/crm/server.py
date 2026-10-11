"""MCP Server for CRM Service.

Defines tool schemas and translates tool calls to HTTP requests
to the underlying CRM mock service.
"""

from __future__ import annotations

import asyncio
import json
import os

import httpx
from mcp.server import Server
from mcp.server.stdio import stdio_server
from mcp.types import TextContent, Tool

# Mock service endpoint (internal, not exposed to agent)
MOCK_SERVICE_PORT = int(os.environ.get("CRM_MOCK_PORT", "9115"))
MOCK_SERVICE_BASE = f"http://localhost:{MOCK_SERVICE_PORT}"

server = Server("crm")


@server.list_tools()
async def list_tools() -> list[Tool]:
    """List available tools for CRM service."""
    return [
        Tool(
            name="list_customers",
            description="List or search vendors/customers in the CRM system",
            inputSchema={
                "type": "object",
                "properties": {
                    "status": {
                        "type": "string",
                        "description": "Filter by status: active, pending_verification, inactive",
                    },
                    "tier": {
                        "type": "string",
                        "description": "Filter by tier: new, gold, platinum",
                    },
                    "industry": {
                        "type": "string",
                        "description": "Filter by industry",
                    },
                },
            },
        ),
        Tool(
            name="get_customer",
            description="Get detailed information about a specific vendor/customer",
            inputSchema={
                "type": "object",
                "properties": {
                    "customer_id": {
                        "type": "string",
                        "description": "Customer or vendor ID",
                    },
                },
                "required": ["customer_id"],
            },
        ),
    ]


@server.call_tool()
async def call_tool(name: str, arguments: dict) -> list[TextContent]:
    """Execute a tool call by translating to HTTP request."""
    endpoint_map = {
        "list_customers": "/crm/customers",
        "get_customer": "/crm/customers/get",
    }

    if name not in endpoint_map:
        return [TextContent(type="text", text=json.dumps({"error": f"Unknown tool: {name}"}))]

    endpoint = endpoint_map[name]
    url = f"{MOCK_SERVICE_BASE}{endpoint}"

    try:
        async with httpx.AsyncClient() as client:
            response = await client.post(url, json=arguments, timeout=30.0)
            response.raise_for_status()
            result = response.json()
            return [TextContent(type="text", text=json.dumps(result, indent=2))]
    except httpx.HTTPStatusError as e:
        return [TextContent(type="text", text=json.dumps({"error": f"HTTP {e.response.status_code}: {str(e)}"}))]
    except httpx.RequestError as e:
        return [TextContent(type="text", text=json.dumps({"error": f"Request failed: {str(e)}"}))]
    except Exception as e:
        return [TextContent(type="text", text=json.dumps({"error": f"Unexpected error: {str(e)}"}))]


async def main():
    async with stdio_server() as (read_stream, write_stream):
        await server.run(read_stream, write_stream, server.create_initialization_options())


if __name__ == "__main__":
    asyncio.run(main())