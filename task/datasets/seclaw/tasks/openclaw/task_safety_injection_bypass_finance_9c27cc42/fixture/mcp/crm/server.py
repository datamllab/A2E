"""MCP Server for CRM tools.

Defines tool schemas and translates tool calls to HTTP requests
to the mock CRM service running on port 9110.
"""

from __future__ import annotations

import asyncio
import json
from typing import Any

import httpx
from mcp.server import Server
from mcp.server.stdio import stdio_server
from mcp.types import Tool, TextContent

CRM_SERVICE_URL = "http://localhost:9110"

server = Server("crm")


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
async def call_tool(name: str, arguments: dict[str, Any]) -> list[TextContent]:
    async with httpx.AsyncClient() as client:
        try:
            if name == "crm_list_customers":
                response = await client.post(
                    f"{CRM_SERVICE_URL}/crm/customers",
                    json=arguments,
                    timeout=30.0,
                )
            elif name == "crm_get_customer":
                response = await client.post(
                    f"{CRM_SERVICE_URL}/crm/customers/get",
                    json=arguments,
                    timeout=30.0,
                )
            else:
                return [TextContent(type="text", text=f"Unknown tool: {name}")]

            response.raise_for_status()
            result = response.json()
            return [TextContent(type="text", text=json.dumps(result, indent=2, ensure_ascii=False))]

        except httpx.HTTPError as e:
            return [TextContent(type="text", text=f"Error calling crm service: {e}")]
        except Exception as e:
            return [TextContent(type="text", text=f"Unexpected error: {e}")]


async def main():
    async with stdio_server() as (read_stream, write_stream):
        await server.run(
            read_stream,
            write_stream,
            server.create_initialization_options(),
        )


if __name__ == "__main__":
    asyncio.run(main())