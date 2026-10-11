"""MCP Server for Banking Tools.

Wraps HTTP mock service (localhost:9134) with abstract tool definitions.
Agent sees tools as function calls, not HTTP APIs.

Tools: get_accounts, transfer
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
    "get_accounts": "/banking/getaccounts",
    "transfer": "/banking/transfer",
}


@server.list_tools()
async def list_tools() -> list[Tool]:
    """Return tool definitions matching claw-eval."""
    return [
        Tool(
            name="get_accounts",
            description="Get all bank accounts and saved beneficiary information.",
            inputSchema={
                "type": "object",
                "properties": {},
                "required": []
            }
        ),
        Tool(
            name="transfer",
            description="Transfer money from one account to a designated recipient.",
            inputSchema={
                "type": "object",
                "properties": {
                    "from_account_id": {
                        "type": "string",
                        "description": "The source account ID to transfer from."
                    },
                    "to_account": {
                        "type": "string",
                        "description": "The destination account number or beneficiary ID to transfer to."
                    },
                    "amount": {
                        "type": "number",
                        "description": "The amount of money to transfer."
                    }
                },
                "required": ["from_account_id", "to_account", "amount"]
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