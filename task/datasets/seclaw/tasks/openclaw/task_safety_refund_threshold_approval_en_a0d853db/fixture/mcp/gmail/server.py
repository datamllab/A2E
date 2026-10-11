"""MCP server for gmail service."""

import json
import httpx
from mcp.server import Server
from mcp.server.stdio import stdio_server
from mcp.types import Tool, TextContent

SERVER_NAME = "gmail"
PORT = 9100
BASE_URL = f"http://localhost:{PORT}"

server = Server(SERVER_NAME)


@server.list_tools()
async def list_tools() -> list[Tool]:
    return [
        Tool(
            name="gmail_list_messages",
            description="List messages in the inbox with optional date range and result limit",
            inputSchema={
                "type": "object",
                "properties": {
                    "days_back": {
                        "type": "integer",
                        "description": "Number of days to look back",
                        "default": 7,
                    },
                    "max_results": {
                        "type": "integer",
                        "description": "Maximum number of results to return",
                        "default": 20,
                    },
                },
                "required": [],
            },
        ),
        Tool(
            name="gmail_get_message",
            description="Get detailed content of a specific email by message ID",
            inputSchema={
                "type": "object",
                "properties": {
                    "message_id": {
                        "type": "string",
                        "description": "Message ID",
                    },
                },
                "required": ["message_id"],
            },
        ),
        Tool(
            name="gmail_send_message",
            description="Send an email to a specified recipient",
            inputSchema={
                "type": "object",
                "properties": {
                    "to": {
                        "type": "string",
                        "description": "Recipient email address",
                    },
                    "subject": {
                        "type": "string",
                        "description": "Email subject",
                    },
                    "body": {
                        "type": "string",
                        "description": "Email body",
                    },
                },
                "required": ["to", "subject", "body"],
            },
        ),
        Tool(
            name="gmail_save_draft",
            description="Save an email as a draft, optionally as a reply to an existing message",
            inputSchema={
                "type": "object",
                "properties": {
                    "to": {
                        "type": "string",
                        "description": "Recipient email address",
                    },
                    "subject": {
                        "type": "string",
                        "description": "Email subject",
                    },
                    "body": {
                        "type": "string",
                        "description": "Email body",
                    },
                    "reply_to_message_id": {
                        "type": "string",
                        "description": "Original message ID if this is a reply",
                    },
                },
                "required": ["to", "subject", "body"],
            },
        ),
    ]


@server.call_tool()
async def call_tool(name: str, arguments: dict):
    async with httpx.AsyncClient(timeout=30.0) as client:
        if name == "gmail_list_messages":
            resp = await client.post(f"{BASE_URL}/gmail/messages", json=arguments)
        elif name == "gmail_get_message":
            resp = await client.post(f"{BASE_URL}/gmail/messages/get", json=arguments)
        elif name == "gmail_send_message":
            resp = await client.post(f"{BASE_URL}/gmail/send", json=arguments)
        elif name == "gmail_save_draft":
            resp = await client.post(f"{BASE_URL}/gmail/drafts/save", json=arguments)
        else:
            return [TextContent(type="text", text=json.dumps({"error": f"Unknown tool: {name}"}))]

        return [TextContent(type="text", text=json.dumps(resp.json(), indent=2))]


async def main():
    async with stdio_server() as (read_stream, write_stream):
        await server.run(read_stream, write_stream, server.create_initialization_options())


if __name__ == "__main__":
    import asyncio
    asyncio.run(main())