"""MCP Server for Finance Tools.

Wraps HTTP mock service (localhost:9106) with abstract tool definitions.
Agent sees tools as function calls, not HTTP APIs.

Tools: GetBalance, SendPayment, RequestPayment, GetTransactions, GetFriends
"""

import json
import httpx
from mcp.server import Server
from mcp.server.stdio import stdio_server
from mcp.types import Tool, TextContent

# Create MCP server instance
server = Server("finance")

# HTTP mock service base URL (internal - not exposed to agent)
HTTP_BASE_URL = "http://localhost:9106"

# Tool-to-endpoint mapping (internal)
TOOL_ENDPOINTS = {
    "GetBalance": "/finance/getbalance",
    "SendPayment": "/finance/sendpayment",
    "RequestPayment": "/finance/requestpayment",
    "GetTransactions": "/finance/gettransactions",
    "GetFriends": "/finance/getfriends",
}


@server.list_tools()
async def list_tools() -> list[Tool]:
    """Return tool definitions matching claw-eval."""
    return [
        Tool(
            name="GetBalance",
            description="Get balance.",
            inputSchema={
                "type": "object",
                "properties": {},
                "required": [],
            },
        ),
        Tool(
            name="SendPayment",
            description="Send payment.",
            inputSchema={
                "type": "object",
                "properties": {
                    "to": {
                        "type": "string",
                        "description": "The recipient to send payment to.",
                    },
                    "amount": {
                        "type": "number",
                        "description": "The amount to send.",
                    },
                    "note": {
                        "type": "string",
                        "description": "A note for the payment.",
                    },
                },
                "required": ["to", "amount"],
            },
        ),
        Tool(
            name="RequestPayment",
            description="Request payment.",
            inputSchema={
                "type": "object",
                "properties": {
                    "from": {
                        "type": "string",
                        "description": "The person to request payment from.",
                    },
                    "amount": {
                        "type": "number",
                        "description": "The amount to request.",
                    },
                },
                "required": ["from", "amount"],
            },
        ),
        Tool(
            name="GetTransactions",
            description="Get transaction history.",
            inputSchema={
                "type": "object",
                "properties": {
                    "limit": {
                        "type": "integer",
                        "description": "The maximum number of transactions to return.",
                    },
                },
                "required": [],
            },
        ),
        Tool(
            name="GetFriends",
            description="Get friends list.",
            inputSchema={
                "type": "object",
                "properties": {
                    "limit": {
                        "type": "integer",
                        "description": "The maximum number of friends to return.",
                    },
                },
                "required": [],
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