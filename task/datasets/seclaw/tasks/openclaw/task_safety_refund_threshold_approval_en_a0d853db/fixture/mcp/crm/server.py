"""MCP server for CRM service."""

import json
import httpx
from mcp.server import Server
from mcp.server.stdio import stdio_server
from mcp.types import Tool, TextContent

SERVER_NAME = "crm"
PORT = 9110
BASE_URL = f"http://localhost:{PORT}"

server = Server(SERVER_NAME)


@server.list_tools()
async def list_tools() -> list[Tool]:
    return [
        Tool(
            name="crm_list_customers",
            description="List customers with optional filters for status, tier, or industry",
            inputSchema={
                "type": "object",
                "properties": {
                    "status": {
                        "type": "string",
                        "description": "Filter by status (active/churned)",
                    },
                    "tier": {
                        "type": "string",
                        "description": "Filter by tier (vip/standard)",
                    },
                    "industry": {
                        "type": "string",
                        "description": "Filter by industry",
                    },
                },
                "required": [],
            },
        ),
        Tool(
            name="crm_get_customer",
            description="Get detailed customer information by customer ID",
            inputSchema={
                "type": "object",
                "properties": {
                    "customer_id": {
                        "type": "string",
                        "description": "Customer ID",
                    },
                },
                "required": ["customer_id"],
            },
        ),
    ]


@server.call_tool()
async def call_tool(name: str, arguments: dict):
    async with httpx.AsyncClient(timeout=30.0) as client:
        if name == "crm_list_customers":
            resp = await client.post(f"{BASE_URL}/crm/customers", json=arguments)
        elif name == "crm_get_customer":
            resp = await client.post(f"{BASE_URL}/crm/customers/get", json=arguments)
        else:
            return [TextContent(type="text", text=json.dumps({"error": f"Unknown tool: {name}"}))]

        return [TextContent(type="text", text=json.dumps(resp.json(), indent=2))]


async def main():
    async with stdio_server() as (read_stream, write_stream):
        await server.run(read_stream, write_stream, server.create_initialization_options())


if __name__ == "__main__":
    import asyncio
    asyncio.run(main())