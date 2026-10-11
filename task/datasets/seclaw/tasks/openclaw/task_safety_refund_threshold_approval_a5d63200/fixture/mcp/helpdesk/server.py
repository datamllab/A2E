"""MCP Server for Helpdesk Tools.

Wraps HTTP mock service (localhost:9107) with abstract tool definitions.

Tools: helpdesk_list_tickets, helpdesk_get_ticket, helpdesk_update_ticket
"""

import json
import httpx
from mcp.server import Server
from mcp.server.stdio import stdio_server
from mcp.types import Tool, TextContent

server = Server("helpdesk")

HTTP_BASE_URL = "http://localhost:9107"

TOOL_ENDPOINTS = {
    "helpdesk_list_tickets": "/helpdesk/tickets",
    "helpdesk_get_ticket": "/helpdesk/tickets/get",
    "helpdesk_update_ticket": "/helpdesk/tickets/update",
}


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
        Tool(
            name="helpdesk_update_ticket",
            description="更新工单信息",
            inputSchema={
                "type": "object",
                "properties": {
                    "ticket_id": {
                        "type": "string",
                        "description": "工单ID",
                    },
                    "priority": {
                        "type": "string",
                        "description": "优先级 (low/medium/high/critical)",
                    },
                    "tags": {
                        "type": "array",
                        "items": {"type": "string"},
                        "description": "标签列表",
                    },
                    "category": {
                        "type": "string",
                        "description": "工单分类",
                    },
                },
                "required": ["ticket_id"],
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