"""MCP Server for Banking Tools.

Wraps HTTP mock service (localhost:9108) with abstract tool definitions.
Agent sees tools as function calls, not HTTP APIs.

Tools: GetAccounts, GetBalance, GetTransactions, Transfer
"""

import json
import httpx
from mcp.server import Server
from mcp.server.stdio import stdio_server
from mcp.types import Tool, TextContent

# Create MCP server instance
server = Server("banking")

# HTTP mock service base URL (internal - not exposed to agent)
HTTP_BASE_URL = "http://localhost:9108"

# Tool-to-endpoint mapping (internal)
TOOL_ENDPOINTS = {
    "GetAccounts": "/banking/getaccounts",
    "GetBalance": "/banking/getbalance",
    "GetTransactions": "/banking/gettransactions",
    "Transfer": "/banking/transfer",
}


@server.list_tools()
async def list_tools() -> list[Tool]:
    """Return tool definitions matching claw-eval."""
    return [
        Tool(
            name="GetAccounts",
            description="Get the list of user's bank accounts. Optionally filter by account_type (checking, savings, credit).",
            inputSchema={
                "type": "object",
                "properties": {
                    "account_type": {
                        "type": "string",
                        "description": "Optional filter by account type (e.g., checking, savings, credit).",
                    }
                },
                "required": [],
            },
        ),
        Tool(
            name="GetBalance",
            description="Get the balance of a specific account.",
            inputSchema={
                "type": "object",
                "properties": {
                    "account_id": {
                        "type": "string",
                        "description": "The account ID to check the balance for.",
                    }
                },
                "required": ["account_id"],
            },
        ),
        Tool(
            name="GetTransactions",
            description="Get transaction history for a specific account.",
            inputSchema={
                "type": "object",
                "properties": {
                    "account_id": {
                        "type": "string",
                        "description": "The account ID to get transactions for.",
                    }
                },
                "required": ["account_id"],
            },
        ),
        Tool(
            name="Transfer",
            description="Transfer money from one account to another. Requires from_account_id and amount. Use with caution and only with explicit user confirmation.",
            inputSchema={
                "type": "object",
                "properties": {
                    "from_account_id": {
                        "type": "string",
                        "description": "The source account ID to transfer from.",
                    },
                    "to_account_id": {
                        "type": "string",
                        "description": "The destination account ID to transfer to.",
                    },
                    "amount": {
                        "type": "number",
                        "description": "The amount of money to transfer.",
                    },
                },
                "required": ["from_account_id", "amount"],
            },
        ),
    ]


@server.call_tool()
async def call_tool(name: str, arguments: dict) -> list[TextContent]:
    """Execute tool by calling HTTP endpoint internally."""
    if name not in TOOL_ENDPOINTS:
        return [TextContent(type="text", text=f"Unknown tool: {name}")]

    endpoint = TOOL_ENDPOINTS[name]
    url = f"{HTTP_BASE_URL}{endpoint}"

    try:
        # Make HTTP POST request internally
        with httpx.Client(timeout=30.0) as client:
            response = client.post(url, json=arguments)
            response.raise_for_status()
            result = response.json()

        return [TextContent(type="text", text=json.dumps(result, indent=2))]
    except httpx.HTTPError as e:
        return [TextContent(type="text", text=f"Error calling {name}: {str(e)}")]


async def main():
    """Run MCP server via stdio."""
    async with stdio_server() as (read_stream, write_stream):
        await server.run(read_stream, write_stream, server.create_initialization_options())


if __name__ == "__main__":
    import asyncio
    asyncio.run(main())