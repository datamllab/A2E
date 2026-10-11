"""MCP Server for helpdesk tools.

Defines tool schemas and translates tool calls to HTTP requests
to the mock helpdesk service running on port 9107.
"""

from __future__ import annotations

import asyncio
import json
from typing import Any

import httpx
from mcp.server import Server
from mcp.server.stdio import stdio_server
from mcp.types import Tool, TextContent

HELPDESK_SERVICE_URL = "http://localhost:9107"

server = Server("helpdesk")


@server.list_tools()
async def list_tools() -> list[Tool]:
    return [
        Tool(
            name="helpdesk_list_tickets",
            description="获取工单列表",
            inputSchema={
                "type": "object",
                "properties": {
                    "status": {
                        "type": "string",
                        "description": "按状态筛选 (open/closed/all)",
                        "default": "open",
                    },
                },
                "required": [],
            },
        ),
        Tool(
            name="helpdesk_get_ticket",
            description="获取工单详细信息",
            inputSchema={
                "type": "object",
                "properties": {
                    "ticket_id": {
                        "type": "string",
                        "description": "工单ID",
                    },
                },
                "required": ["ticket_id"],
            },
        ),
    ]


@server.call_tool()
async def call_tool(name: str, arguments: dict[str, Any]) -> list[TextContent]:
    async with httpx.AsyncClient() as client:
        try:
            if name == "helpdesk_list_tickets":
                response = await client.post(
                    f"{HELPDESK_SERVICE_URL}/helpdesk/tickets",
                    json=arguments,
                    timeout=30.0,
                )
            elif name == "helpdesk_get_ticket":
                response = await client.post(
                    f"{HELPDESK_SERVICE_URL}/helpdesk/tickets/get",
                    json=arguments,
                    timeout=30.0,
                )
            else:
                return [TextContent(type="text", text=f"Unknown tool: {name}")]

            response.raise_for_status()
            result = response.json()
            return [TextContent(type="text", text=json.dumps(result, indent=2, ensure_ascii=False))]

        except httpx.HTTPError as e:
            return [TextContent(type="text", text=f"Error calling helpdesk service: {e}")]
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