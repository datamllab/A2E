#!/usr/bin/env python3
"""MCP Server for Banking - wraps HTTP mock service with tool schema.

Provides GetAccounts and Transfer tools to the agent while internally
calling the HTTP mock service on localhost:9134.
"""

import asyncio
import json
import httpx
from mcp.server import Server
from mcp.server.stdio import stdio_server
from mcp.types import Tool, TextContent

MOCK_SERVICE_URL = "http://localhost:9134"

app = Server("banking")


@app.list_tools()
async def list_tools() -> list[Tool]:
    return [
        Tool(
            name="GetAccounts",
            description="Get accounts.",
            inputSchema={
                "type": "object",
                "properties": {},
                "required": []
            }
        ),
        Tool(
            name="Transfer",
            description="Transfer money.",
            inputSchema={
                "type": "object",
                "properties": {
                    "from_account_id": {
                        "type": "string",
                        "description": "The source account ID to transfer from."
                    },
                    "amount": {
                        "type": "number",
                        "description": "The amount of money to transfer."
                    }
                },
                "required": ["from_account_id", "amount"]
            }
        ),
    ]


@app.call_tool()
async def call_tool(name: str, arguments: dict) -> list[TextContent]:
    async with httpx.AsyncClient(timeout=30.0) as client:
        try:
            if name == "GetAccounts":
                response = await client.post(
                    f"{MOCK_SERVICE_URL}/banking/getaccounts",
                    json=arguments
                )
                response.raise_for_status()
                result = response.json()
                return [TextContent(type="text", text=json.dumps(result, indent=2, ensure_ascii=False))]
            elif name == "Transfer":
                response = await client.post(
                    f"{MOCK_SERVICE_URL}/banking/transfer",
                    json=arguments
                )
                response.raise_for_status()
                result = response.json()
                return [TextContent(type="text", text=json.dumps(result, indent=2, ensure_ascii=False))]
            else:
                return [TextContent(type="text", text=json.dumps({"error": f"Unknown tool: {name}"}))]
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