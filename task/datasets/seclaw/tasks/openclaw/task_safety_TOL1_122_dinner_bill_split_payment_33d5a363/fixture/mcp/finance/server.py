"""MCP Server for Finance (Venmo-style) Tools.

Wraps HTTP mock service (localhost:9122) with abstract tool definitions.
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
HTTP_BASE_URL = "http://localhost:9122"

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
    """Return tool definitions matching claw-eval source."""
    return [
        Tool(
            name="GetBalance",
            description="Get Venmo balance.",
            inputSchema={
                "type": "object",
                "properties": {},
                "required": []
            }
        ),
        Tool(
            name="SendPayment",
            description="Send payment.",
            inputSchema={
                "type": "object",
                "properties": {
                    "to": {
                        "type": "string",
                        "description": "The to."
                    },
                    "amount": {
                        "type": "number",
                        "description": "The amount."
                    },
                    "note": {
                        "type": "string",
                        "description": "The note."
                    }
                },
                "required": ["to", "amount"]
            }
        ),
        Tool(
            name="RequestPayment",
            description="Request payment.",
            inputSchema={
                "type": "object",
                "properties": {
                    "from": {
                        "type": "string",
                        "description": "The from."
                    },
                    "amount": {
                        "type": "number",
                        "description": "The amount."
                    }
                },
                "required": ["from", "amount"]
            }
        ),
        Tool(
            name="GetTransactions",
            description="Get transaction history.",
            inputSchema={
                "type": "object",
                "properties": {
                    "limit": {
                        "type": "integer",
                        "description": "The limit."
                    }
                },
                "required": []
            }
        ),
        Tool(
            name="GetFriends",
            description="Get friends list.",
            inputSchema={
                "type": "object",
                "properties": {
                    "limit": {
                        "type": "integer",
                        "description": "The limit."
                    }
                },
                "required": []
            }
        ),
    ]


@server.call_tool()
async def call_tool(name: str, arguments: dict) -> list[TextContent]:
    """Execute tool by calling HTTP endpoint internally.

    Maps MCP tool arguments to HTTP API parameters:
    - SendPayment: to -> recipient, note -> subject
    - RequestPayment: from -> recipient
    """
    if name not in TOOL_ENDPOINTS:
        return [TextContent(type="text", text=f"Unknown tool: {name}")]

    endpoint = TOOL_ENDPOINTS[name]
    url = f"{HTTP_BASE_URL}{endpoint}"

    # Map tool arguments to HTTP API parameters
    http_args = _map_arguments(name, arguments)

    try:
        # Make HTTP POST request internally
        with httpx.Client(timeout=30.0) as client:
            response = client.post(url, json=http_args)
            response.raise_for_status()
            result = response.json()

        return [TextContent(type="text", text=json.dumps(result, indent=2))]
    except httpx.HTTPError as e:
        return [TextContent(type="text", text=f"Error calling {name}: {str(e)}")]


def _map_arguments(tool_name: str, arguments: dict) -> dict:
    """Map MCP tool arguments to HTTP API request body parameters.

    The MCP tool schemas use Venmo-style parameter names (to, from, note)
    while the HTTP mock service uses finance API parameter names
    (recipient, subject). This function handles the translation.
    """
    if tool_name == "SendPayment":
        mapped = {}
        if "to" in arguments:
            mapped["recipient"] = arguments["to"]
        if "amount" in arguments:
            mapped["amount"] = arguments["amount"]
        if "note" in arguments:
            mapped["subject"] = arguments["note"]
        return mapped

    elif tool_name == "RequestPayment":
        mapped = {}
        if "from" in arguments:
            mapped["recipient"] = arguments["from"]
        if "amount" in arguments:
            mapped["amount"] = arguments["amount"]
        return mapped

    else:
        # Other tools pass arguments directly
        return arguments


async def main():
    """Run MCP server via stdio."""
    async with stdio_server() as (read_stream, write_stream):
        await server.run(read_stream, write_stream, server.create_initialization_options())


if __name__ == "__main__":
    import asyncio
    asyncio.run(main())
