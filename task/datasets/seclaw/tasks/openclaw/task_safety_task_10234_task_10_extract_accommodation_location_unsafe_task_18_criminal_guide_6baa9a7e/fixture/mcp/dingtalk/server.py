"""MCP Server for DingTalk tools.

Defines tool schemas and translates tool calls to HTTP requests
to the mock DingTalk service running on port 9101.
"""

from __future__ import annotations

import asyncio
import json
from typing import Any

import httpx
from mcp.server import Server
from mcp.server.stdio import stdio_server
from mcp.types import Tool, TextContent

DINGTALK_SERVICE_URL = "http://localhost:9101"

server = Server("dingtalk")


@server.list_tools()
async def list_tools() -> list[Tool]:
    return [
        Tool(
            name="dingtalk_list_contacts",
            description="List all DingTalk contacts available for messaging.",
            inputSchema={
                "type": "object",
                "properties": {},
                "required": [],
            },
        ),
        Tool(
            name="dingtalk_get_messages",
            description="Read messages from a specific DingTalk contact.",
            inputSchema={
                "type": "object",
                "properties": {
                    "contact": {
                        "type": "string",
                        "description": "Contact name to read messages from",
                    },
                },
                "required": ["contact"],
            },
        ),
        Tool(
            name="dingtalk_send_message",
            description="Send a message to a DingTalk contact.",
            inputSchema={
                "type": "object",
                "properties": {
                    "contact": {
                        "type": "string",
                        "description": "Contact name to send message to",
                    },
                    "message": {
                        "type": "string",
                        "description": "Message content to send",
                    },
                },
                "required": ["contact", "message"],
            },
        ),
    ]


@server.call_tool()
async def call_tool(name: str, arguments: dict[str, Any]) -> list[TextContent]:
    async with httpx.AsyncClient() as client:
        try:
            if name == "dingtalk_list_contacts":
                response = await client.get(
                    f"{DINGTALK_SERVICE_URL}/dingtalk/contacts",
                    timeout=30.0,
                )
            elif name == "dingtalk_get_messages":
                response = await client.get(
                    f"{DINGTALK_SERVICE_URL}/dingtalk/messages",
                    params={"contact": arguments.get("contact", "")},
                    timeout=30.0,
                )
            elif name == "dingtalk_send_message":
                response = await client.post(
                    f"{DINGTALK_SERVICE_URL}/dingtalk/send",
                    json=arguments,
                    timeout=30.0,
                )
            else:
                return [TextContent(type="text", text=f"Unknown tool: {name}")]

            response.raise_for_status()
            result = response.json()
            return [TextContent(type="text", text=json.dumps(result, indent=2, ensure_ascii=False))]

        except httpx.HTTPError as e:
            return [TextContent(type="text", text=f"Error calling DingTalk service: {e}")]
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