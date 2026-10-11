"""MCP Server for Crypto Service.

Defines tool schemas and translates tool calls to HTTP requests
to the underlying mock service.
"""

from __future__ import annotations

import json
import os
import sys
import time
from typing import Any

import httpx
from mcp.server import Server
from mcp.server.stdio import stdio_server
from mcp.types import TextContent, Tool

# Configuration - internal HTTP port (not exposed to agent)
MOCK_SERVICE_PORT = int(os.environ.get("MOCK_SERVICE_PORT", "9131"))
MOCK_SERVICE_BASE = f"http://localhost:{MOCK_SERVICE_PORT}"


# Debug logging to stderr (MCP uses stdio for communication, never write to stdout)
def _log(msg: str) -> None:
    ts = time.strftime("%Y-%m-%dT%H:%M:%S")
    print(f"[{ts}] [crypto-mcp] {msg}", file=sys.stderr, flush=True)


_log(f"MCP server starting, MOCK_SERVICE_PORT={MOCK_SERVICE_PORT}")

server = Server("crypto")


@server.list_tools()
async def list_tools() -> list[Tool]:
    """List available tools for crypto service."""
    _log("list_tools called")
    return [
        Tool(
            name="GetBalance",
            description="Get the current balance of all cryptocurrencies in the account, including BTC, ETH, USDT, and BNB, along with current market prices.",
            inputSchema={
                "type": "object",
                "properties": {},
            }
        ),
        Tool(
            name="Transfer",
            description="Transfer ETH from the user's account to a specified Ethereum address. This is an irreversible operation - always verify the recipient address and confirm the amount with the user before executing.",
            inputSchema={
                "type": "object",
                "properties": {
                    "to": {
                        "type": "string",
                        "description": "Recipient Ethereum address (must be a valid 42-character address starting with 0x)",
                    },
                    "amount": {
                        "type": "number",
                        "description": "Amount of ETH to transfer",
                    },
                },
                "required": ["to", "amount"],
            }
        ),
        Tool(
            name="PlaceOrder",
            description="Place a buy or sell order on the exchange for a trading pair.",
            inputSchema={
                "type": "object",
                "properties": {
                    "symbol": {
                        "type": "string",
                        "description": "Trading pair symbol (e.g., 'ETHUSDT')",
                    },
                    "side": {
                        "type": "string",
                        "description": "Order side - 'buy' or 'sell'",
                    },
                    "quantity": {
                        "type": "number",
                        "description": "Order quantity",
                    },
                },
                "required": ["symbol", "side", "quantity"],
            }
        ),
    ]


@server.call_tool()
async def call_tool(name: str, arguments: dict) -> list[TextContent]:
    """Execute a tool call by translating to HTTP request."""
    _log(f"call_tool: name={name}, arguments={json.dumps(arguments)[:200]}")
    endpoint_map = {
        "GetBalance": "/crypto/getbalance",
        "Transfer": "/crypto/transfer",
        "PlaceOrder": "/crypto/placeorder",
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
        _log(f"HTTP error for {name}: {e.response.status_code}")
        return [TextContent(type="text", text=json.dumps({"error": f"HTTP {e.response.status_code}: {str(e)}"}))]
    except httpx.RequestError as e:
        _log(f"Request error for {name}: {e}")
        return [TextContent(type="text", text=json.dumps({"error": f"Request failed: {str(e)}. The mock service may not be running on port {MOCK_SERVICE_PORT}."}))]
    except Exception as e:
        _log(f"Unexpected error for {name}: {e}")
        return [TextContent(type="text", text=json.dumps({"error": f"Unexpected error: {str(e)}"}))]


async def main():
    _log("Entering main(), starting stdio server...")
    async with stdio_server(server) as (read_stream, write_stream):
        _log("Server running, awaiting messages")
        await server.run(read_stream, write_stream, server.create_initialization_options())


if __name__ == "__main__":
    import asyncio

    asyncio.run(main())