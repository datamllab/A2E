"""MCP Server for Banking Tools.

Wraps HTTP mock service (localhost:9134) with abstract tool definitions.
Agent sees tools as function calls, not HTTP APIs.

Tools: get_accounts, get_balance, get_transactions, transfer, add_beneficiary
"""

import json
import httpx
from mcp.server import Server
from mcp.server.stdio import stdio_server
from mcp.types import Tool, TextContent

# Create MCP server instance
server = Server("banking")

# HTTP mock service base URL (internal - not exposed to agent)
HTTP_BASE_URL = "http://localhost:9134"

# Tool-to-endpoint mapping (internal)
TOOL_ENDPOINTS = {
    "get_accounts": "/banking/accounts",
    "get_balance": "/banking/balance",
    "get_transactions": "/banking/transactions",
    "transfer": "/banking/transfer",
    "add_beneficiary": "/banking/beneficiary/add",
}


@server.list_tools()
async def list_tools() -> list[Tool]:
    """Return tool definitions matching claw-eval."""
    return [
        Tool(
            name="get_accounts",
            description="Get list of bank accounts, optionally filtered by type.",
            inputSchema={
                "type": "object",
                "properties": {
                    "account_type": {
                        "type": "string",
                        "description": "Filter by type: checking, savings, credit"
                    }
                },
                "required": []
            }
        ),
        Tool(
            name="get_balance",
            description="Get account balance for a specific account.",
            inputSchema={
                "type": "object",
                "properties": {
                    "account_id": {
                        "type": "string",
                        "description": "Account ID to check"
                    }
                },
                "required": ["account_id"]
            }
        ),
        Tool(
            name="get_transactions",
            description="Get recent transactions for an account.",
            inputSchema={
                "type": "object",
                "properties": {
                    "account_id": {
                        "type": "string",
                        "description": "Account ID"
                    },
                    "limit": {
                        "type": "integer",
                        "description": "Number of transactions"
                    },
                    "start_date": {
                        "type": "string",
                        "description": "Start date filter"
                    },
                    "end_date": {
                        "type": "string",
                        "description": "End date filter"
                    }
                },
                "required": ["account_id"]
            }
        ),
        Tool(
            name="transfer",
            description="Transfer funds between accounts or to external recipients.",
            inputSchema={
                "type": "object",
                "properties": {
                    "from_account_id": {
                        "type": "string",
                        "description": "Source account ID"
                    },
                    "to_account_id": {
                        "type": "string",
                        "description": "Internal destination account ID"
                    },
                    "to_external": {
                        "type": "string",
                        "description": "External recipient identifier"
                    },
                    "amount": {
                        "type": "number",
                        "description": "Transfer amount"
                    },
                    "description": {
                        "type": "string",
                        "description": "Transfer description"
                    }
                },
                "required": ["from_account_id", "amount"]
            }
        ),
        Tool(
            name="add_beneficiary",
            description="Add a new payee/beneficiary for future payments.",
            inputSchema={
                "type": "object",
                "properties": {
                    "name": {
                        "type": "string",
                        "description": "Beneficiary name"
                    },
                    "account_number": {
                        "type": "string",
                        "description": "Beneficiary account number"
                    },
                    "bank_name": {
                        "type": "string",
                        "description": "Beneficiary bank name"
                    },
                    "routing_number": {
                        "type": "string",
                        "description": "Routing number"
                    }
                },
                "required": ["name", "account_number", "bank_name"]
            }
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