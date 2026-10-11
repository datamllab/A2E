"""MCP Server for finance tools.

Defines tool schemas and translates tool calls to HTTP requests
to the mock finance service running on port 9104.
"""

from __future__ import annotations

import asyncio
import json
from typing import Any

import httpx
from mcp.server import Server
from mcp.server.stdio import stdio_server
from mcp.types import Tool, TextContent

FINANCE_SERVICE_URL = "http://localhost:9104"

server = Server("finance")


@server.list_tools()
async def list_tools() -> list[Tool]:
    return [
        Tool(
            name="finance_list_transactions",
            description="获取财务交易记录列表",
            inputSchema={
                "type": "object",
                "properties": {
                    "start_date": {
                        "type": "string",
                        "description": "开始日期 (YYYY-MM-DD)",
                    },
                    "end_date": {
                        "type": "string",
                        "description": "结束日期 (YYYY-MM-DD)",
                    },
                },
                "required": [],
            },
        ),
        Tool(
            name="finance_get_transaction",
            description="获取财务交易详情",
            inputSchema={
                "type": "object",
                "properties": {
                    "transaction_id": {
                        "type": "string",
                        "description": "交易ID",
                    },
                },
                "required": ["transaction_id"],
            },
        ),
    ]


@server.call_tool()
async def call_tool(name: str, arguments: dict[str, Any]) -> list[TextContent]:
    async with httpx.AsyncClient() as client:
        try:
            if name == "finance_list_transactions":
                response = await client.post(
                    f"{FINANCE_SERVICE_URL}/finance/transactions",
                    json=arguments,
                    timeout=30.0,
                )
            elif name == "finance_get_transaction":
                response = await client.post(
                    f"{FINANCE_SERVICE_URL}/finance/transactions/get",
                    json=arguments,
                    timeout=30.0,
                )
            else:
                return [TextContent(type="text", text=f"Unknown tool: {name}")]

            response.raise_for_status()
            result = response.json()
            return [TextContent(type="text", text=json.dumps(result, indent=2, ensure_ascii=False))]

        except httpx.HTTPError as e:
            return [TextContent(type="text", text=f"Error calling finance service: {e}")]
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