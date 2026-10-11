"""MCP Server for Finance Tools.

Wraps HTTP mock service (localhost:9104) with abstract tool definitions.

Tools: finance_list_transactions, finance_get_transaction
"""

import json
import httpx
from mcp.server import Server
from mcp.server.stdio import stdio_server
from mcp.types import Tool, TextContent

server = Server("finance")

HTTP_BASE_URL = "http://localhost:9104"

TOOL_ENDPOINTS = {
    "finance_list_transactions": "/finance/transactions",
    "finance_get_transaction": "/finance/transactions/get",
}


@server.list_tools()
async def list_tools() -> list[Tool]:
    return [
        Tool(
            name="finance_list_transactions",
            description="List finance transactions with optional filters.",
            inputSchema={
                "type": "object",
                "properties": {
                    "start_date": {"type": "string", "description": "Start date filter (YYYY-MM-DD)"},
                    "end_date": {"type": "string", "description": "End date filter (YYYY-MM-DD)"},
                },
                "required": [],
            }
        ),
        Tool(
            name="finance_get_transaction",
            description="Get transaction details by transaction ID.",
            inputSchema={
                "type": "object",
                "properties": {
                    "transaction_id": {"type": "string", "description": "The transaction ID to retrieve"},
                },
                "required": ["transaction_id"],
            }
        ),
    ]


@server.call_tool()
async def call_tool(name: str, arguments: dict) -> list[TextContent]:
    if name not in TOOL_ENDPOINTS:
        return [TextContent(type="text", text=f"Unknown tool: {name}")]

    endpoint = TOOL_ENDPOINTS[name]
    url = f"{HTTP_BASE_URL}{endpoint}"

    try:
        with httpx.Client(timeout=30.0) as client:
            response = client.post(url, json=arguments)
            response.raise_for_status()
            result = response.json()
        return [TextContent(type="text", text=json.dumps(result, indent=2))]
    except httpx.HTTPError as e:
        return [TextContent(type="text", text=f"Error calling {name}: {str(e)}")]


async def main():
    async with stdio_server() as (read_stream, write_stream):
        await server.run(read_stream, write_stream, server.create_initialization_options())


if __name__ == "__main__":
    import asyncio
    asyncio.run(main())
