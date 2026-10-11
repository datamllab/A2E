"""MCP Server for banking tools.

Defines tool schemas and translates tool calls to HTTP requests
to the mock banking service running on port 9102.
"""

from __future__ import annotations

import asyncio
import json
from typing import Any

import httpx
from mcp.server import Server
from mcp.server.stdio import stdio_server
from mcp.types import Tool, TextContent

# HTTP endpoint for the mock banking service (internal, not exposed to Agent)
BANKING_SERVICE_URL = "http://localhost:9102"

server = Server("banking")


@server.list_tools()
async def list_tools() -> list[Tool]:
    """Define available banking tools."""
    return [
        Tool(
            name="banking_login",
            description="Login to banking system",
            inputSchema={
                "type": "object",
                "properties": {
                    "username": {
                        "type": "string",
                        "description": "Login username",
                    },
                    "password": {
                        "type": "string",
                        "description": "Login password",
                    },
                },
                "required": ["username", "password"],
            },
        ),
        Tool(
            name="banking_get_accounts",
            description="Get list of bank accounts",
            inputSchema={
                "type": "object",
                "properties": {},
                "required": [],
            },
        ),
        Tool(
            name="banking_transfer",
            description="Transfer money",
            inputSchema={
                "type": "object",
                "properties": {
                    "to_account": {
                        "type": "string",
                        "description": "Destination account number",
                    },
                    "amount": {
                        "type": "number",
                        "description": "Amount to transfer",
                    },
                },
                "required": ["to_account", "amount"],
            },
        ),
    ]


@server.call_tool()
async def call_tool(name: str, arguments: dict[str, Any]) -> list[TextContent]:
    """Execute tool call by translating to HTTP request to mock service."""
    async with httpx.AsyncClient() as client:
        try:
            if name == "banking_login":
                response = await client.post(
                    f"{BANKING_SERVICE_URL}/banking/login",
                    json=arguments,
                    timeout=30.0,
                )
                response.raise_for_status()
                result = response.json()
                return [TextContent(type="text", text=json.dumps(result, indent=2, ensure_ascii=False))]

            elif name == "banking_get_accounts":
                response = await client.get(
                    f"{BANKING_SERVICE_URL}/banking/health",
                    timeout=30.0,
                )
                response.raise_for_status()
                result = response.json()
                return [TextContent(type="text", text=json.dumps(result, indent=2, ensure_ascii=False))]

            elif name == "banking_transfer":
                response = await client.post(
                    f"{BANKING_SERVICE_URL}/banking/transfer",
                    json=arguments,
                    timeout=30.0,
                )
                response.raise_for_status()
                result = response.json()
                return [TextContent(type="text", text=json.dumps(result, indent=2, ensure_ascii=False))]

            else:
                return [TextContent(type="text", text=f"Unknown tool: {name}")]

        except httpx.HTTPError as e:
            return [TextContent(type="text", text=f"Error calling banking service: {e}")]
        except Exception as e:
            return [TextContent(type="text", text=f"Unexpected error: {e}")]


async def main():
    async with stdio_server() as (read_stream, write_stream):
        await server.run(
            read_stream,
            write_stream,
            server.create_initialization_options(),
        )


if __name__ == "__main__":
    asyncio.run(main())