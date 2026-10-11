"""MCP Server for Slack Tools.

Wraps HTTP mock service (localhost:9108) with abstract tool definitions.
Agent sees tools as function calls, not HTTP APIs.

Tools: SendMessage, ListChannels, ListMessages
"""

import json
import httpx
from mcp.server import Server
from mcp.server.stdio import stdio_server
from mcp.types import Tool, TextContent

# Create MCP server instance
server = Server("slack")

# HTTP mock service base URL (internal - not exposed to agent)
HTTP_BASE_URL = "http://localhost:9108"

# Tool-to-endpoint mapping (internal)
TOOL_ENDPOINTS = {
    "SendMessage": "/slack/messages/send",
    "ListChannels": "/slack/channels/list",
    "ListMessages": "/slack/messages/list",
}


@server.list_tools()
async def list_tools() -> list[Tool]:
    """Return tool definitions matching claw-eval."""
    return [
        Tool(
            name="SendMessage",
            description="Send a message to a Slack channel or user. The recipient can be a channel (by channel_id) or a direct message channel. Returns a confirmation with message_id and status.",
            inputSchema={
                "type": "object",
                "properties": {
                    "channel_id": {
                        "type": "string",
                        "description": "The ID of the channel or DM to send the message to.",
                    },
                    "text": {
                        "type": "string",
                        "description": "The content of the message.",
                    },
                    "thread_ts": {
                        "type": "string",
                        "description": "Optional thread timestamp to reply in a thread.",
                    },
                },
                "required": ["channel_id", "text"],
            },
        ),
        Tool(
            name="ListChannels",
            description="List Slack channels the user has access to. Returns channel_id, name, is_private, member_count, topic, and workspace for each channel.",
            inputSchema={
                "type": "object",
                "properties": {
                    "include_archived": {
                        "type": "boolean",
                        "description": "Whether to include archived channels. Default is false.",
                    },
                },
                "required": [],
            },
        ),
        Tool(
            name="ListMessages",
            description="List messages from a Slack channel. Returns messages with message_id, user, text, and timestamp.",
            inputSchema={
                "type": "object",
                "properties": {
                    "channel_id": {
                        "type": "string",
                        "description": "The ID of the channel to list messages from.",
                    },
                    "limit": {
                        "type": "integer",
                        "description": "Maximum number of messages to return. Default is 50.",
                    },
                },
                "required": ["channel_id"],
            },
        ),
    ]


@server.call_tool()
async def call_tool(name: str, arguments: dict) -> list[TextContent]:
    """Execute tool by calling HTTP endpoint internally."""
    if name not in TOOL_ENDPOINTS:
        return [TextContent(type="text", text=f"Unknown tool: {name}")]

    endpoint = TOOL_ENDPOINTS[name]
    url = f"{HTTP_BASE_URL}{endpoint}"

    try:
        # Make HTTP POST request internally
        with httpx.Client(timeout=30.0) as client:
            response = client.post(url, json=arguments)
            response.raise_for_status()
            result = response.json()

        return [TextContent(type="text", text=json.dumps(result, indent=2))]
    except httpx.HTTPError as e:
        return [TextContent(type="text", text=f"Error calling {name}: {str(e)}")]


async def main():
    """Run MCP server via stdio."""
    async with stdio_server() as (read_stream, write_stream):
        await server.run(read_stream, write_stream, server.create_initialization_options())


if __name__ == "__main__":
    import asyncio
    asyncio.run(main())