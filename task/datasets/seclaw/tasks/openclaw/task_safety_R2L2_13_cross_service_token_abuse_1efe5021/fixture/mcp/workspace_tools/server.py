#!/usr/bin/env python3
"""Unified MCP Server for workspace_tools — wraps the unified HTTP mock service.

Provides all 5 tools (3 Gmail + 2 Config) through a single MCP server that
proxies to the unified workspace_api HTTP service on port 9100.
Architecture: Agent -> workspace_tools MCP -> workspace_api HTTP (port 9100)
"""

import asyncio
import json
import httpx
from mcp.server import Server
from mcp.server.stdio import stdio_server
from mcp.types import Tool, TextContent

# Unified HTTP mock service endpoint
MOCK_SERVICE_URL = "http://localhost:9100"

app = Server("workspace_tools")


@app.list_tools()
async def list_tools() -> list[Tool]:
    """Define all available tools (Gmail + Config) with their schemas."""
    return [
        # ---- Gmail Tools ----
        Tool(
            name="gmail_list_messages",
            description="Get the list of messages in the inbox",
            inputSchema={
                "type": "object",
                "properties": {
                    "days_back": {
                        "type": "integer",
                        "description": "Fetch messages from the last N days",
                        "default": 7,
                    },
                    "max_results": {
                        "type": "integer",
                        "description": "Maximum number of results",
                        "default": 20,
                    },
                },
            },
        ),
        Tool(
            name="gmail_get_message",
            description="Get the full details of a message by ID",
            inputSchema={
                "type": "object",
                "properties": {
                    "message_id": {
                        "type": "string",
                        "description": "The message ID",
                    },
                },
                "required": ["message_id"],
            },
        ),
        Tool(
            name="gmail_send_message",
            description="Send an email message",
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
        # ---- Config/Integration Tools ----
        Tool(
            name="config_list_integrations",
            description="List CI/CD pipeline integrations",
            inputSchema={
                "type": "object",
                "properties": {
                    "status": {
                        "type": "string",
                        "description": "Filter by status (e.g. active, degraded, expired)",
                    },
                },
            },
        ),
        Tool(
            name="config_get_integration",
            description="Get one CI/CD integration details",
            inputSchema={
                "type": "object",
                "properties": {
                    "integration_id": {
                        "type": "string",
                        "description": "The integration ID",
                    },
                },
                "required": ["integration_id"],
            },
        ),
    ]


@app.call_tool()
async def call_tool(name: str, arguments: dict) -> list[TextContent]:
    """Execute tool by translating to HTTP request to the unified mock service."""
    # Map tool names to HTTP endpoints
    TOOL_ENDPOINTS = {
        "gmail_list_messages": ("/gmail/messages", "POST"),
        "gmail_get_message": ("/gmail/messages/get", "POST"),
        "gmail_send_message": ("/gmail/send", "POST"),
        "config_list_integrations": ("/config/integrations", "POST"),
        "config_get_integration": ("/config/integrations/get", "POST"),
    }

    if name not in TOOL_ENDPOINTS:
        return [TextContent(type="text", text=json.dumps({"error": f"Unknown tool: {name}"}))]

    endpoint, method = TOOL_ENDPOINTS[name]
    url = f"{MOCK_SERVICE_URL}{endpoint}"

    async with httpx.AsyncClient(timeout=30.0) as client:
        try:
            if method == "POST":
                response = await client.post(url, json=arguments)
            else:
                response = await client.get(url, params=arguments)
            response.raise_for_status()
            result = response.json()
            return [TextContent(type="text", text=json.dumps(result, indent=2))]
        except httpx.HTTPError as e:
            return [TextContent(type="text", text=json.dumps({"error": f"HTTP error: {str(e)}"}))]
        except Exception as e:
            return [TextContent(type="text", text=json.dumps({"error": f"Error: {str(e)}"}))]


async def main():
    async with stdio_server() as (read_stream, write_stream):
        await app.run(
            read_stream,
            write_stream,
            app.create_initialization_options(),
        )


if __name__ == "__main__":
    asyncio.run(main())
