"""MCP Finance Server - Translates tool calls to HTTP requests.

This MCP server defines tool schemas and internally translates tool calls
to HTTP requests to the mock finance service. The Agent does not see the
HTTP implementation details.
"""

from typing import Any
import json
import httpx
from mcp.server import Server
from mcp.server.stdio import stdio_server
from mcp.types import Tool, TextContent


# Server instance
server = Server("finance")

# HTTP endpoint for mock service (internal, not exposed to Agent)
MOCK_SERVICE_URL = "http://localhost:9106"


@server.list_tools()
async def list_tools() -> list[Tool]:
    """List available finance tools."""
    return [
        Tool(
            name="GetBalance",
            description="Get the current payment platform balance for the user account.",
            inputSchema={
                "type": "object",
                "properties": {},
                "required": []
            }
        ),
        Tool(
            name="SendPayment",
            description="Send a payment to another user.",
            inputSchema={
                "type": "object",
                "properties": {
                    "to": {
                        "type": "string",
                        "description": "The recipient's username"
                    },
                    "amount": {
                        "type": "number",
                        "description": "The amount to send"
                    },
                    "note": {
                        "type": "string",
                        "description": "Optional note for the payment"
                    }
                },
                "required": ["to", "amount"]
            }
        ),
        Tool(
            name="RequestPayment",
            description="Request a payment from another user.",
            inputSchema={
                "type": "object",
                "properties": {
                    "from": {
                        "type": "string",
                        "description": "The user's username to request payment from"
                    },
                    "amount": {
                        "type": "number",
                        "description": "The amount to request"
                    }
                },
                "required": ["from", "amount"]
            }
        ),
        Tool(
            name="GetTransactions",
            description="Get the transaction history.",
            inputSchema={
                "type": "object",
                "properties": {
                    "limit": {
                        "type": "integer",
                        "description": "Maximum number of transactions to return"
                    }
                },
                "required": []
            }
        ),
        Tool(
            name="GetFriends",
            description="Get the list of friends.",
            inputSchema={
                "type": "object",
                "properties": {
                    "limit": {
                        "type": "integer",
                        "description": "Maximum number of friends to return"
                    }
                },
                "required": []
            }
        ),
    ]


@server.call_tool()
async def call_tool(name: str, arguments: dict[str, Any]) -> list[TextContent]:
    """Handle tool calls by translating to HTTP requests."""
    try:
        if name == "GetBalance":
            async with httpx.AsyncClient() as client:
                response = await client.post(f"{MOCK_SERVICE_URL}/finance/getbalance", json={})
                response.raise_for_status()
                result = response.json()

        elif name == "SendPayment":
            async with httpx.AsyncClient() as client:
                response = await client.post(
                    f"{MOCK_SERVICE_URL}/finance/sendpayment",
                    json={
                        "to": arguments.get("to"),
                        "amount": arguments.get("amount"),
                        "note": arguments.get("note", "")
                    }
                )
                response.raise_for_status()
                result = response.json()

        elif name == "RequestPayment":
            async with httpx.AsyncClient() as client:
                response = await client.post(
                    f"{MOCK_SERVICE_URL}/finance/requestpayment",
                    json={
                        "from": arguments.get("from"),
                        "amount": arguments.get("amount")
                    }
                )
                response.raise_for_status()
                result = response.json()

        elif name == "GetTransactions":
            async with httpx.AsyncClient() as client:
                payload = {}
                if "limit" in arguments:
                    payload["limit"] = arguments["limit"]
                response = await client.post(
                    f"{MOCK_SERVICE_URL}/finance/gettransactions",
                    json=payload
                )
                response.raise_for_status()
                result = response.json()

        elif name == "GetFriends":
            async with httpx.AsyncClient() as client:
                payload = {}
                if "limit" in arguments:
                    payload["limit"] = arguments["limit"]
                response = await client.post(
                    f"{MOCK_SERVICE_URL}/finance/getfriends",
                    json=payload
                )
                response.raise_for_status()
                result = response.json()

        else:
            result = {"error": f"Unknown tool: {name}"}

        return [TextContent(type="text", text=json.dumps(result, indent=2))]

    except httpx.HTTPError as e:
        return [TextContent(type="text", text=json.dumps({"error": str(e)}))]
    except Exception as e:
        return [TextContent(type="text", text=json.dumps({"error": f"Internal error: {str(e)}"}))]


async def main():
    async with stdio_server() as (read_stream, write_stream):
        await server.run(
            read_stream,
            write_stream,
            server.create_initialization_options()
        )


if __name__ == "__main__":
    import asyncio
    asyncio.run(main())