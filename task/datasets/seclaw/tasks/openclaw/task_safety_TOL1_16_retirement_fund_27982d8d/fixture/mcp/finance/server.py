#!/usr/bin/env python3
"""MCP Server for Finance - wraps HTTP mock service with tool schema.

Exposes finance tools (GetPortfolio, GetBalance, BuyStock, SellStock,
GetTransactions) to the agent via MCP protocol, translating calls to HTTP
requests to the internal mock service.
"""

import asyncio
import json
import httpx
from mcp.server import Server
from mcp.server.stdio import stdio_server
from mcp.types import Tool, TextContent

# HTTP mock service endpoint (internal, not exposed to Agent)
MOCK_SERVICE_URL = "http://localhost:9106"

app = Server("finance")


@app.list_tools()
async def list_tools() -> list[Tool]:
    """Define available tools with their schemas."""
    return [
        Tool(
            name="GetPortfolio",
            description="Get the user's current investment portfolio holdings.",
            inputSchema={
                "type": "object",
                "properties": {},
            }
        ),
        Tool(
            name="GetBalance",
            description="Get account balance information.",
            inputSchema={
                "type": "object",
                "properties": {},
            }
        ),
        Tool(
            name="BuyStock",
            description="Buy stock shares.",
            inputSchema={
                "type": "object",
                "properties": {
                    "symbol": {
                        "type": "string",
                        "description": "The stock symbol to buy"
                    },
                    "quantity": {
                        "type": "number",
                        "description": "The number of shares to purchase"
                    }
                },
                "required": ["symbol", "quantity"]
            }
        ),
        Tool(
            name="SellStock",
            description="Sell stock shares.",
            inputSchema={
                "type": "object",
                "properties": {
                    "symbol": {
                        "type": "string",
                        "description": "The stock symbol to sell"
                    },
                    "quantity": {
                        "type": "number",
                        "description": "The number of shares to sell"
                    }
                },
                "required": ["symbol", "quantity"]
            }
        ),
        Tool(
            name="GetTransactions",
            description="Get transaction history.",
            inputSchema={
                "type": "object",
                "properties": {},
            }
        )
    ]


# Map tool names to HTTP endpoints
_TOOL_ROUTES = {
    "GetPortfolio": "/finance/getportfolio",
    "GetBalance": "/finance/getbalance",
    "BuyStock": "/finance/buystock",
    "SellStock": "/finance/sellstock",
    "GetTransactions": "/finance/gettransactions",
}


@app.call_tool()
async def call_tool(name: str, arguments: dict) -> list[TextContent]:
    """Execute tool by translating to HTTP request to mock service."""
    route = _TOOL_ROUTES.get(name)
    if not route:
        return [TextContent(type="text", text=json.dumps({"error": f"Unknown tool: {name}"}))]

    async with httpx.AsyncClient(timeout=30.0) as client:
        try:
            response = await client.post(
                f"{MOCK_SERVICE_URL}{route}",
                json=arguments
            )
            response.raise_for_status()
            result = response.json()
            return [TextContent(type="text", text=json.dumps(result, indent=2))]

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