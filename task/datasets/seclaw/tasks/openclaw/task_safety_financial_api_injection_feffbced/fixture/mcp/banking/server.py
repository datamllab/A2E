"""MCP Server for Banking tools.

Translates MCP tool calls into HTTP requests to the internal banking mock service.
Agent sees only abstract tool definitions; HTTP URLs/ports are never exposed.
"""

from __future__ import annotations

import json
import sys

import httpx
from mcp.server import Server
from mcp.server.stdio import stdio_server
from mcp.types import TextContent, Tool

SERVER_NAME = "banking"
HTTP_BASE_URL = "http://localhost:9102"

server = Server(SERVER_NAME)

TOOL_DEFINITIONS = [
    Tool(
        name="get_balance",
        description="Get account balance for a given account ID",
        inputSchema={
            "type": "object",
            "properties": {
                "account_id": {
                    "type": "string",
                    "description": "Account ID to check",
                },
            },
            "required": ["account_id"],
        },
    ),
    Tool(
        name="list_transactions",
        description="List recent transactions for a given account",
        inputSchema={
            "type": "object",
            "properties": {
                "account_id": {
                    "type": "string",
                    "description": "Account ID",
                },
                "days": {
                    "type": "integer",
                    "description": "Number of days to look back",
                },
            },
            "required": ["account_id"],
        },
    ),
    Tool(
        name="add_beneficiary",
        description="Add a new beneficiary to the user's account",
        inputSchema={
            "type": "object",
            "properties": {
                "account_id": {
                    "type": "string",
                    "description": "User's account ID",
                },
                "beneficiary_name": {
                    "type": "string",
                    "description": "Beneficiary name",
                },
                "beneficiary_account": {
                    "type": "string",
                    "description": "Beneficiary account number",
                },
            },
            "required": ["account_id", "beneficiary_name", "beneficiary_account"],
        },
    ),
]

TOOL_ENDPOINTS = {
    "get_balance": ("/banking/balance", "POST"),
    "list_transactions": ("/banking/transactions", "POST"),
    "add_beneficiary": ("/banking/beneficiary/add", "POST"),
}


@server.list_tools()
async def list_tools() -> list[Tool]:
    return TOOL_DEFINITIONS


@server.call_tool()
async def call_tool(name: str, arguments: dict):
    if name not in TOOL_ENDPOINTS:
        return [TextContent(type="text", text=f"Error: Unknown tool '{name}'")]

    endpoint, method = TOOL_ENDPOINTS[name]
    url = f"{HTTP_BASE_URL}{endpoint}"

    try:
        with httpx.Client(timeout=30.0) as client:
            if method == "POST":
                response = client.post(url, json=arguments)
            else:
                response = client.get(url, params=arguments)

        if response.status_code >= 400:
            return [TextContent(type="text", text=f"Error: HTTP {response.status_code} - {response.text}")]

        return [TextContent(type="text", text=json.dumps(response.json(), indent=2))]
    except httpx.ConnectError:
        return [TextContent(type="text", text="Error: Could not connect to banking service")]
    except Exception as e:
        return [TextContent(type="text", text=f"Error: {str(e)}")]


async def main():
    async with stdio_server() as (read_stream, write_stream):
        await server.run(read_stream, write_stream, server.create_initialization_options())


if __name__ == "__main__":
    import asyncio
    asyncio.run(main())
