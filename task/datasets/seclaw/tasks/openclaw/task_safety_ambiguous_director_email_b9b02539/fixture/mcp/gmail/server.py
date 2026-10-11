#!/usr/bin/env python3
"""MCP Server for Gmail - wraps HTTP mock service with tool schema."""

import asyncio
import json
import httpx
from mcp.server import Server
from mcp.server.stdio import stdio_server
from mcp.types import Tool, TextContent

# HTTP mock service endpoint
MOCK_SERVICE_URL = "http://localhost:9100"

app = Server("gmail")


@app.list_tools()
async def list_tools() -> list[Tool]:
    """Define available tools with their schemas."""
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
                        "default": 7
                    },
                    "max_results": {
                        "type": "integer",
                        "description": "最大返回数量",
                        "default": 20
                    }
                },
                "required": []
            }
        ),
        Tool(
            name="gmail_get_message",
            description="根据邮件ID获取邮件详细内容",
            inputSchema={
                "type": "object",
                "properties": {
                    "message_id": {
                        "type": "string",
                        "description": "邮件ID"
                    }
                },
                "required": ["message_id"]
            }
        ),
        Tool(
            name="gmail_send_message",
            description="发送邮件",
            inputSchema={
                "type": "object",
                "properties": {
                    "to": {
                        "type": "string",
                        "description": "收件人邮箱地址"
                    },
                    "subject": {
                        "type": "string",
                        "description": "邮件主题"
                    },
                    "body": {
                        "type": "string",
                        "description": "邮件正文"
                    }
                },
                "required": ["to", "subject", "body"]
            }
        ),
        Tool(
            name="gmail_save_draft",
            description="将邮件保存为草稿",
            inputSchema={
                "type": "object",
                "properties": {
                    "to": {
                        "type": "string",
                        "description": "收件人邮箱地址"
                    },
                    "subject": {
                        "type": "string",
                        "description": "邮件主题"
                    },
                    "body": {
                        "type": "string",
                        "description": "邮件正文"
                    },
                    "reply_to_message_id": {
                        "type": "string",
                        "description": "如果是回复邮件，原邮件ID"
                    }
                },
                "required": ["to", "subject", "body"]
            }
        ),
    ]


@app.call_tool()
async def call_tool(name: str, arguments: dict) -> list[TextContent]:
    """Execute tool by translating to HTTP request to mock service."""
    endpoint_map = {
        "gmail_list_messages": "/gmail/messages",
        "gmail_get_message": "/gmail/messages/get",
        "gmail_send_message": "/gmail/send",
        "gmail_save_draft": "/gmail/drafts/save",
    }

    endpoint = endpoint_map.get(name)
    if endpoint is None:
        return [TextContent(type="text", text=json.dumps({"error": f"Unknown tool: {name}"}))]

    async with httpx.AsyncClient(timeout=30.0) as client:
        try:
            response = await client.post(
                f"{MOCK_SERVICE_URL}{endpoint}",
                json=arguments
            )
            response.raise_for_status()
            result = response.json()
            return [TextContent(type="text", text=json.dumps(result, indent=2, ensure_ascii=False))]

        except httpx.HTTPError as e:
            return [TextContent(type="text", text=json.dumps({"error": f"HTTP error: {str(e)}"}))]
        except Exception as e:
            return [TextContent(type="text", text=json.dumps({"error": f"Error: {str(e)}"}))]


async def main():
    async with stdio_server() as (read_stream, write_stream):
        await app.run(
            read_stream,
            write_stream,
            app.create_initialization_options()
        )


if __name__ == "__main__":
    asyncio.run(main())