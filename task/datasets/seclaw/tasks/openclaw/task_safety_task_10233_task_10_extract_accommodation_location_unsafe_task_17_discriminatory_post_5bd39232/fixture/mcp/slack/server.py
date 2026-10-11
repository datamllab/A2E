"""MCP Server for Slack/DingTalk Tools.

Wraps HTTP mock service (localhost:9101) with abstract tool definitions.
Agent sees tools as function calls, not HTTP APIs.

Tools: ListUsers, GetInbox, SendMessage
"""

import json
import httpx
from mcp.server import Server
from mcp.server.stdio import stdio_server
from mcp.types import Tool, TextContent

server = Server("slack")

HTTP_BASE_URL = "http://localhost:9101"

TOOL_ENDPOINTS = {
    "ListUsers": "/slack/users/list",
    "GetInbox": "/slack/messages/inbox",
    "SendMessage": "/slack/send",
}


@server.list_tools()
async def list_tools() -> list[Tool]:
    return [
        Tool(
            name="ListUsers",
            description="List available contacts in the workspace. Returns a list of usernames.",
            inputSchema={
                "type": "object",
                "properties": {},
                "required": []
            }
        ),
        Tool(
            name="GetInbox",
            description="Get inbox messages for a user. Returns messages sent to the specified user.",
            inputSchema={
                "type": "object",
                "properties": {
                    "user": {
                        "type": "string",
                        "description": "Username whose inbox to retrieve"
                    }
                },
                "required": ["user"]
            }
        ),
        Tool(
            name="SendMessage",
            description="Send a message to a contact in the workspace.",
            inputSchema={
                "type": "object",
                "properties": {
                    "user_id": {
                        "type": "string",
                        "description": "Username of the recipient"
                    },
                    "message": {
                        "type": "string",
                        "description": "Message content to send"
                    }
                },
                "required": ["user_id", "message"]
            }
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