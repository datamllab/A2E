"""MCP Server for gmail tools.

Defines tool schemas and translates tool calls to HTTP requests
to the mock gmail service running on port 9100.
"""

from __future__ import annotations

import asyncio
import json
from typing import Any

import httpx
from mcp.server import Server
from mcp.server.stdio import stdio_server
from mcp.types import Tool, TextContent

# HTTP endpoint for the mock gmail service (internal, not exposed to Agent)
GMAIL_SERVICE_URL = "http://localhost:9100"

server = Server("gmail")


@server.list_tools()
async def list_tools() -> list[Tool]:
    """Define available gmail tools."""
    return [
        Tool(
            name="gmail_list_messages",
            description="获取收件箱中的邮件列表",
            inputSchema={
                "type": "object",
                "properties": {
                    "days_back": {
                        "type": "integer",
                        "description": "获取最近几天的邮件",
                        "default": 7,
                    },
                    "max_results": {
                        "type": "integer",
                        "description": "最大返回数量",
                        "default": 20,
                    },
                },
                "required": [],
            },
        ),
        Tool(
            name="gmail_get_message",
            description="根据邮件ID获取邮件详细内容",
            inputSchema={
                "type": "object",
                "properties": {
                    "message_id": {
                        "type": "string",
                        "description": "邮件ID",
                    },
                },
                "required": ["message_id"],
            },
        ),
        Tool(
            name="gmail_send_message",
            description="发送邮件",
            inputSchema={
                "type": "object",
                "properties": {
                    "to": {
                        "type": "string",
                        "description": "收件人邮箱地址",
                    },
                    "subject": {
                        "type": "string",
                        "description": "邮件主题",
                    },
                    "body": {
                        "type": "string",
                        "description": "邮件正文",
                    },
                },
                "required": ["to", "subject", "body"],
            },
        ),
        Tool(
            name="gmail_save_draft",
            description="将邮件保存为草稿",
            inputSchema={
                "type": "object",
                "properties": {
                    "to": {
                        "type": "string",
                        "description": "收件人邮箱地址",
                    },
                    "subject": {
                        "type": "string",
                        "description": "邮件主题",
                    },
                    "body": {
                        "type": "string",
                        "description": "邮件正文",
                    },
                    "reply_to_message_id": {
                        "type": "string",
                        "description": "如果是回复邮件，原邮件ID",
                    },
                },
                "required": ["to", "subject", "body"],
            },
        ),
    ]


@server.call_tool()
async def call_tool(name: str, arguments: dict[str, Any]) -> list[TextContent]:
    """Execute tool call by translating to HTTP request to mock service."""
    async with httpx.AsyncClient() as client:
        try:
            if name == "gmail_list_messages":
                response = await client.post(
                    f"{GMAIL_SERVICE_URL}/gmail/messages",
                    json=arguments,
                    timeout=30.0,
                )
                response.raise_for_status()
                result = response.json()
                return [TextContent(type="text", text=json.dumps(result, indent=2, ensure_ascii=False))]

            elif name == "gmail_get_message":
                response = await client.post(
                    f"{GMAIL_SERVICE_URL}/gmail/messages/get",
                    json=arguments,
                    timeout=30.0,
                )
                response.raise_for_status()
                result = response.json()
                return [TextContent(type="text", text=json.dumps(result, indent=2, ensure_ascii=False))]

            elif name == "gmail_send_message":
                response = await client.post(
                    f"{GMAIL_SERVICE_URL}/gmail/send",
                    json=arguments,
                    timeout=30.0,
                )
                response.raise_for_status()
                result = response.json()
                return [TextContent(type="text", text=json.dumps(result, indent=2, ensure_ascii=False))]

            elif name == "gmail_save_draft":
                response = await client.post(
                    f"{GMAIL_SERVICE_URL}/gmail/drafts/save",
                    json=arguments,
                    timeout=30.0,
                )
                response.raise_for_status()
                result = response.json()
                return [TextContent(type="text", text=json.dumps(result, indent=2, ensure_ascii=False))]

            else:
                return [TextContent(type="text", text=f"Unknown tool: {name}")]

        except httpx.HTTPError as e:
            return [TextContent(type="text", text=f"Error calling gmail service: {e}")]
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