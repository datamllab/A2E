"""MCP Server for Gmail Tools.

Wraps HTTP mock service (localhost:9100) with abstract tool definitions.
Agent sees tools as function calls, not HTTP APIs.

Tools: gmail_list_messages, gmail_get_message, gmail_send_message, gmail_save_draft
"""

import json
import httpx
from mcp.server import Server
from mcp.server.stdio import stdio_server
from mcp.types import Tool, TextContent

server = Server("gmail")

HTTP_BASE_URL = "http://localhost:9100"

TOOL_ENDPOINTS = {
    "gmail_list_messages": "/gmail/messages",
    "gmail_get_message": "/gmail/messages/get",
    "gmail_send_message": "/gmail/send",
    "gmail_save_draft": "/gmail/drafts/save",
}


@server.list_tools()
async def list_tools() -> list[Tool]:
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