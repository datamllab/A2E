"""MCP Server for calendar tools.

Defines tool schemas and translates tool calls to HTTP requests
to the mock calendar service running on port 9101.
"""

from __future__ import annotations

import asyncio
import json
from typing import Any

import httpx
from mcp.server import Server
from mcp.server.stdio import stdio_server
from mcp.types import Tool, TextContent

# HTTP endpoint for the mock calendar service (internal, not exposed to Agent)
CALENDAR_SERVICE_URL = "http://localhost:9101"

server = Server("calendar")


@server.list_tools()
async def list_tools() -> list[Tool]:
    """Define available calendar tools."""
    return [
        Tool(
            name="calendar_list_events",
            description="获取指定日期范围内的日历事件",
            inputSchema={
                "type": "object",
                "properties": {
                    "date": {
                        "type": "string",
                        "description": "开始日期 (YYYY-MM-DD)",
                    },
                    "days": {
                        "type": "integer",
                        "description": "查看几天的日程",
                        "default": 1,
                    },
                },
                "required": ["date"],
            },
        ),
        Tool(
            name="calendar_get_user_events",
            description="获取指定用户在指定日期的日程",
            inputSchema={
                "type": "object",
                "properties": {
                    "user": {
                        "type": "string",
                        "description": "用户邮箱",
                    },
                    "date": {
                        "type": "string",
                        "description": "日期 (YYYY-MM-DD)",
                    },
                },
                "required": ["user", "date"],
            },
        ),
    ]


@server.call_tool()
async def call_tool(name: str, arguments: dict[str, Any]) -> list[TextContent]:
    """Execute tool call by translating to HTTP request to mock service."""
    async with httpx.AsyncClient() as client:
        try:
            if name == "calendar_list_events":
                response = await client.post(
                    f"{CALENDAR_SERVICE_URL}/calendar/events",
                    json=arguments,
                    timeout=30.0,
                )
                response.raise_for_status()
                result = response.json()
                return [TextContent(type="text", text=json.dumps(result, indent=2, ensure_ascii=False))]

            elif name == "calendar_get_user_events":
                response = await client.post(
                    f"{CALENDAR_SERVICE_URL}/calendar/user_events",
                    json=arguments,
                    timeout=30.0,
                )
                response.raise_for_status()
                result = response.json()
                return [TextContent(type="text", text=json.dumps(result, indent=2, ensure_ascii=False))]

            else:
                return [TextContent(type="text", text=f"Unknown tool: {name}")]

        except httpx.HTTPError as e:
            return [TextContent(type="text", text=f"Error calling calendar service: {e}")]
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