"""MCP Server for CRM Tools.

Wraps HTTP mock service (localhost:9110) with abstract tool definitions.

Tools: crm_list_customers, crm_get_customer
"""

import json
import httpx
from mcp.server import Server
from mcp.server.stdio import stdio_server
from mcp.types import Tool, TextContent

server = Server("crm")

HTTP_BASE_URL = "http://localhost:9110"

TOOL_ENDPOINTS = {
    "crm_list_customers": "/crm/customers",
    "crm_get_customer": "/crm/customers/get",
}


@server.list_tools()
async def list_tools() -> list[Tool]:
    return [
        Tool(
            name="crm_list_customers",
            description="获取客户列表",
            inputSchema={
                "type": "object",
                "properties": {
                    "status": {
                        "type": "string",
                        "description": "按状态筛选 (active/churned)",
                    },
                    "tier": {
                        "type": "string",
                        "description": "按等级筛选 (vip/standard)",
                    },
                    "industry": {
                        "type": "string",
                        "description": "按行业筛选",
                    },
                },
                "required": [],
            },
        ),
        Tool(
            name="crm_get_customer",
            description="获取客户详细信息",
            inputSchema={
                "type": "object",
                "properties": {
                    "customer_id": {
                        "type": "string",
                        "description": "客户ID",
                    },
                },
                "required": ["customer_id"],
            },
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