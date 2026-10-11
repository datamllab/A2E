"""MCP Server for Gmail Tools.

Wraps HTTP mock service (localhost:9123) with abstract tool definitions.
Agent sees tools as function calls, not HTTP APIs.

Tools: SearchEmails, GetEmail, SendEmail
"""

import json
import httpx
from mcp.server import Server
from mcp.server.stdio import stdio_server
from mcp.types import Tool, TextContent

server = Server("gmail")

HTTP_BASE_URL = "http://localhost:9123"

TOOL_ENDPOINTS = {
    "SearchEmails": "/gmail/messages",
    "GetEmail": "/gmail/messages/get",
    "SendEmail": "/gmail/send",
}


@server.list_tools()
async def list_tools() -> list[Tool]:
    return [
        Tool(
            name="SearchEmails",
            description="Searches emails by various criteria. Returns a list of emails with message_id, from, subject, date, is_read, and labels.",
            inputSchema={
                "type": "object",
                "properties": {
                    "days_back": {
                        "type": "integer",
                        "description": "Number of days back to search (default 7).",
                    },
                    "max_results": {
                        "type": "integer",
                        "description": "Maximum number of results to return (default 20).",
                    },
                },
                "required": [],
            },
        ),
        Tool(
            name="GetEmail",
            description="Gets a single email by message_id. Returns full email content including body.",
            inputSchema={
                "type": "object",
                "properties": {
                    "message_id": {
                        "type": "string",
                        "description": "The message ID to retrieve.",
                    },
                },
                "required": ["message_id"],
            },
        ),
        Tool(
            name="SendEmail",
            description="Sends an email to the specified recipient.",
            inputSchema={
                "type": "object",
                "properties": {
                    "to": {
                        "type": "string",
                        "description": "The recipient email address.",
                    },
                    "subject": {
                        "type": "string",
                        "description": "The subject of the email.",
                    },
                    "body": {
                        "type": "string",
                        "description": "The body of the email.",
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