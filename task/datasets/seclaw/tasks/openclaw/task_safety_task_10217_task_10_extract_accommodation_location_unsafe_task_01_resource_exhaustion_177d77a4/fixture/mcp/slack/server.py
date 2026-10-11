"""MCP Server for Slack tools.

Defines tool schemas and translates tool calls to HTTP requests
to the mock Slack service running on port 9101.
"""

from __future__ import annotations

import asyncio
import json
import logging
import sys
import traceback
from typing import Any

import httpx
from mcp.server import Server
from mcp.server.stdio import stdio_server
from mcp.types import Tool, TextContent

# Configure logging to stderr (stdout is used for MCP protocol)
logging.basicConfig(
    stream=sys.stderr,
    level=logging.INFO,
    format="%(asctime)s [slack-mcp] %(levelname)s %(message)s",
)
logger = logging.getLogger("slack-mcp")

SLACK_SERVICE_URL = "http://localhost:9101"

server = Server("slack")


@server.list_tools()
async def list_tools() -> list[Tool]:
    """List available Slack tools."""
    logger.info("list_tools called")
    return [
        Tool(
            name="slack_list_users",
            description="List all available contacts in the workspace.",
            inputSchema={
                "type": "object",
                "properties": {},
                "required": [],
            },
        ),
        Tool(
            name="slack_get_messages",
            description="Get messages from a user's inbox. Provide the username to retrieve their received messages.",
            inputSchema={
                "type": "object",
                "properties": {
                    "user": {
                        "type": "string",
                        "description": "The username whose inbox messages to retrieve",
                    },
                },
                "required": ["user"],
            },
        ),
        Tool(
            name="slack_send_message",
            description="Send a message to a contact in the workspace.",
            inputSchema={
                "type": "object",
                "properties": {
                    "user_id": {
                        "type": "string",
                        "description": "The username of the recipient",
                    },
                    "message": {
                        "type": "string",
                        "description": "The message content to send",
                    },
                },
                "required": ["user_id", "message"],
            },
        ),
    ]


@server.call_tool()
async def call_tool(name: str, arguments: dict[str, Any]) -> list[TextContent]:
    """Handle tool calls by forwarding to the mock Slack HTTP service."""
    logger.info("call_tool: name=%s, arguments=%s", name, json.dumps(arguments, default=str))
    async with httpx.AsyncClient() as client:
        try:
            if name == "slack_list_users":
                response = await client.get(
                    f"{SLACK_SERVICE_URL}/slack/users",
                    timeout=30.0,
                )
            elif name == "slack_get_messages":
                response = await client.get(
                    f"{SLACK_SERVICE_URL}/slack/messages/inbox",
                    params=arguments,
                    timeout=30.0,
                )
            elif name == "slack_send_message":
                response = await client.post(
                    f"{SLACK_SERVICE_URL}/slack/send",
                    json=arguments,
                    timeout=30.0,
                )
            else:
                logger.warning("Unknown tool requested: %s", name)
                return [TextContent(type="text", text=f"Unknown tool: {name}")]

            response.raise_for_status()
            result = response.json()
            logger.info("Tool %s succeeded", name)
            return [TextContent(type="text", text=json.dumps(result, indent=2, ensure_ascii=False))]

        except httpx.HTTPError as e:
            logger.error("HTTP error calling Slack service for %s: %s", name, e)
            return [TextContent(type="text", text=f"Error calling Slack service: {e}")]
        except Exception as e:
            logger.error("Unexpected error in %s: %s", name, e)
            return [TextContent(type="text", text=f"Unexpected error: {e}")]


async def main():
    """Run the MCP server using stdio transport."""
    logger.info("Starting Slack MCP server...")
    try:
        async with stdio_server() as (read_stream, write_stream):
            logger.info("stdio transport established, running server...")
            await server.run(
                read_stream,
                write_stream,
                server.create_initialization_options(),
            )
    except Exception:
        logger.exception("Fatal error in MCP server main loop")
        traceback.print_exc(file=sys.stderr)
        sys.exit(1)


if __name__ == "__main__":
    try:
        asyncio.run(main())
    except Exception:
        logger.exception("Fatal error starting MCP server")
        traceback.print_exc(file=sys.stderr)
        sys.exit(1)