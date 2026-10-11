"""MCP Server for Banking Service.

Defines tool schemas and translates tool calls to HTTP requests
to the underlying banking mock service.
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
MOCK_SERVICE_PORT = int(os.environ.get("BANKING_MOCK_PORT", "9114"))
MOCK_SERVICE_BASE = f"http://localhost:{MOCK_SERVICE_PORT}"

server = Server("banking")


@server.list_tools()
async def list_tools() -> list[Tool]:
    """List available tools for banking service."""
    return [
        Tool(
            name="get_accounts",
            description="Get list of bank accounts, optionally filtered by type",
            inputSchema={
                "type": "object",
                "properties": {
                    "account_type": {
                        "type": "string",
                        "description": "Filter by type: checking, savings, credit",
                    },
                },
            },
        ),
        Tool(
            name="get_balance",
            description="Get account balance",
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
            name="get_transactions",
            description="Get recent transactions for an account",
            inputSchema={
                "type": "object",
                "properties": {
                    "account_id": {
                        "type": "string",
                        "description": "Account ID",
                    },
                    "limit": {
                        "type": "integer",
                        "description": "Number of transactions",
                    },
                    "start_date": {
                        "type": "string",
                        "description": "Start date filter",
                    },
                    "end_date": {
                        "type": "string",
                        "description": "End date filter",
                    },
                },
                "required": ["account_id"],
            },
        ),
        Tool(
            name="transfer",
            description="Transfer funds between accounts or to external recipients",
            inputSchema={
                "type": "object",
                "properties": {
                    "from_account_id": {
                        "type": "string",
                        "description": "Source account ID",
                    },
                    "to_account_id": {
                        "type": "string",
                        "description": "Internal destination account ID",
                    },
                    "to_external": {
                        "type": "string",
                        "description": "External recipient identifier",
                    },
                    "amount": {
                        "type": "number",
                        "description": "Transfer amount",
                    },
                    "description": {
                        "type": "string",
                        "description": "Transfer description",
                    },
                },
                "required": ["from_account_id", "amount"],
            },
        ),
        Tool(
            name="add_beneficiary",
            description="Add a new payee/beneficiary for future payments",
            inputSchema={
                "type": "object",
                "properties": {
                    "name": {
                        "type": "string",
                        "description": "Beneficiary name",
                    },
                    "account_number": {
                        "type": "string",
                        "description": "Beneficiary account number",
                    },
                    "bank_name": {
                        "type": "string",
                        "description": "Beneficiary bank name",
                    },
                    "routing_number": {
                        "type": "string",
                        "description": "Routing number",
                    },
                },
                "required": ["name", "account_number", "bank_name"],
            },
        ),
    ]


@server.call_tool()
async def call_tool(name: str, arguments: dict) -> list[TextContent]:
    """Execute a tool call by translating to HTTP request."""
    endpoint_map = {
        "get_accounts": "/banking/accounts",
        "get_balance": "/banking/balance",
        "get_transactions": "/banking/transactions",
        "transfer": "/banking/transfer",
        "add_beneficiary": "/banking/beneficiary/add",
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