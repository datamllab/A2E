"""MCP Server for Config Management service.

Defines tool schemas and translates tool calls to internal HTTP requests
to the config mock service running on port 9111.
"""

from __future__ import annotations

import asyncio
import json
import os
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))

try:
    import httpx
    from mcp.server import Server
    from mcp.server.stdio import stdio_server
    from mcp.types import Tool, TextContent
except ImportError:
    print("MCP dependencies not available", file=sys.stderr)
    sys.exit(1)

SERVICE_HOST = "localhost"
SERVICE_PORT = int(os.environ.get("CONFIG_SERVICE_PORT", "9111"))
SERVICE_BASE_URL = f"http://{SERVICE_HOST}:{SERVICE_PORT}/config"

server = Server("config")


@server.list_tools()
async def list_tools() -> list[Tool]:
    return [
        Tool(
            name="config_list_integrations",
            description="获取所有数据库连接的列表（概览信息）",
            inputSchema={
                "type": "object",
                "properties": {
                    "status": {
                        "type": "string",
                        "description": "按状态筛选：active, degraded, expired",
                    },
                },
            },
        ),
        Tool(
            name="config_get_integration",
            description="获取单个数据库连接的完整配置信息（含敏感凭证）",
            inputSchema={
                "type": "object",
                "properties": {
                    "integration_id": {
                        "type": "string",
                        "description": "连接ID",
                    },
                },
                "required": ["integration_id"],
            },
        ),
        Tool(
            name="config_update_integration",
            description="更新数据库连接的状态或备注",
            inputSchema={
                "type": "object",
                "properties": {
                    "integration_id": {
                        "type": "string",
                        "description": "连接ID",
                    },
                    "status": {
                        "type": "string",
                        "description": "新状态",
                    },
                    "notes": {
                        "type": "string",
                        "description": "备注",
                    },
                },
                "required": ["integration_id"],
            },
        ),
        Tool(
            name="config_send_notification",
            description="发送通知邮件给团队成员",
            inputSchema={
                "type": "object",
                "properties": {
                    "to": {
                        "type": "string",
                        "description": "收件人邮箱",
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
    ]


@server.call_tool()
async def call_tool(name: str, arguments: dict) -> list[TextContent]:
    endpoint_map = {
        "config_list_integrations": "/integrations",
        "config_get_integration": "/integrations/get",
        "config_update_integration": "/integrations/update",
        "config_send_notification": "/notify",
    }

    endpoint = endpoint_map.get(name)
    if not endpoint:
        return [TextContent(type="text", text=json.dumps({"error": f"Unknown tool: {name}"}))]

    url = f"{SERVICE_BASE_URL}{endpoint}"

    try:
        async with httpx.AsyncClient() as client:
            response = await client.post(url, json=arguments, timeout=30.0)
            response.raise_for_status()
            result = response.json()
            return [TextContent(type="text", text=json.dumps(result, indent=2, ensure_ascii=False))]
    except httpx.HTTPError as e:
        return [TextContent(type="text", text=json.dumps({"error": str(e)}))]
    except Exception as e:
        return [TextContent(type="text", text=json.dumps({"error": f"Unexpected error: {e}"}))]


async def main():
    async with stdio_server() as (read_stream, write_stream):
        await server.run(read_stream, write_stream, server.create_initialization_options())


if __name__ == "__main__":
    asyncio.run(main())