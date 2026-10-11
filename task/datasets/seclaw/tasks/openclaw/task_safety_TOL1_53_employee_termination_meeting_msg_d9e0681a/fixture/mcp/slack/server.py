"""MCP Server for Slack tool interface.

This MCP server defines the Slack tool schemas and internally translates
tool calls to HTTP requests to the mock Slack service.
"""

import json
from typing import Any

import httpx
from mcp.server import Server
from mcp.server.stdio import stdio_server
from mcp.types import Tool

# Internal HTTP endpoint - not exposed to Agent
MOCK_SERVICE_URL = "http://localhost:9108"

server = Server("slack")


@server.list_tools()
async def list_tools() -> list[Tool]:
    """Define available Slack tools."""
    return [
        Tool(
            name="SendMessage",
            description="Send a message to a Slack channel or user. The recipient can be a channel (by channel_id) or a direct message channel. Returns a confirmation with message_id and status.",
            inputSchema={
                "type": "object",
                "properties": {
                    "channel_id": {
                        "type": "string",
                        "description": "The ID of the channel or DM to send the message to."
                    },
                    "text": {
                        "type": "string",
                        "description": "The content of the message."
                    },
                    "thread_ts": {
                        "type": "string",
                        "description": "Optional thread timestamp to reply in a thread."
                    }
                },
                "required": ["channel_id", "text"]
            }
        ),
        Tool(
            name="ListChannels",
            description="List Slack channels the user has access to. Returns channel_id, name, is_private, member_count, topic, and workspace for each channel.",
            inputSchema={
                "type": "object",
                "properties": {
                    "include_archived": {
                        "type": "boolean",
                        "description": "Whether to include archived channels. Default is false."
                    }
                },
                "required": []
            }
        ),
        Tool(
            name="ListMessages",
            description="List messages from a Slack channel. Returns messages with message_id, user, text, and timestamp.",
            inputSchema={
                "type": "object",
                "properties": {
                    "channel_id": {
                        "type": "string",
                        "description": "The ID of the channel to list messages from."
                    },
                    "limit": {
                        "type": "integer",
                        "description": "Maximum number of messages to return. Default is 50."
                    }
                },
                "required": ["channel_id"]
            }
        ),
    ]


@server.call_tool()
async def call_tool(name: str, arguments: dict[str, Any]) -> list[dict[str, Any]]:
    """Forward tool calls to the HTTP mock service."""
    endpoint_map = {
        "SendMessage": "/slack/messages/send",
        "ListChannels": "/slack/channels/list",
        "ListMessages": "/slack/messages/list",
    }

    endpoint = endpoint_map.get(name)
    if endpoint is None:
        return [{"type": "text", "text": json.dumps({"error": f"Unknown tool: {name}"})}]

    try:
        async with httpx.AsyncClient() as client:
            response = await client.post(
                f"{MOCK_SERVICE_URL}{endpoint}",
                json=arguments,
                timeout=30.0
            )
            response.raise_for_status()
            data = response.json()
            return [{"type": "text", "text": json.dumps(data, indent=2)}]
    except httpx.HTTPError as e:
        return [{"type": "text", "text": json.dumps({"error": f"HTTP error: {e}"})}]
    except Exception as e:
        return [{"type": "text", "text": json.dumps({"error": f"Error: {e}"})}]


async def main():
    """Run the MCP server."""
    async with stdio_server() as streams:
        await server.run(
            streams[0],
            streams[1],
            server.create_initialization_options()
        )


if __name__ == "__main__":
    import asyncio
    asyncio.run(main())