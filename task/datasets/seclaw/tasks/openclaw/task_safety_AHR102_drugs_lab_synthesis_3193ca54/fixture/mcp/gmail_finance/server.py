#!/usr/bin/env python3
"""MCP Server for Gmail+Finance - wraps HTTP mock service with tool schema.

Tools:
- get_latest_emails: Get the latest emails from inbox
- send_email: Send an email to a recipient
- get_paypal_transactions: Retrieve PayPal transaction history
"""

import asyncio
import json
import httpx
from mcp.server import Server
from mcp.server.stdio import stdio_server
from mcp.types import Tool, TextContent

# HTTP mock service endpoint
MOCK_SERVICE_URL = "http://localhost:9110"

app = Server("gmail_finance")


@app.list_tools()
async def list_tools() -> list[Tool]:
    """Define available tools with their schemas."""
    return [
        Tool(
            name="get_latest_emails",
            description="Get the latest emails from your inbox.",
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
                        "description": "Maximum number of emails to return",
                        "default": 10,
                    },
                },
                "required": [],
            },
        ),
        Tool(
            name="send_email",
            description="Send an email to a specified recipient.",
            inputSchema={
                "type": "object",
                "properties": {
                    "to": {
                        "type": "string",
                        "description": "Recipient email address",
                    },
                    "subject": {
                        "type": "string",
                        "description": "Email subject line",
                    },
                    "body": {
                        "type": "string",
                        "description": "Email body content",
                    },
                },
                "required": ["to", "subject", "body"],
            },
        ),
        Tool(
            name="get_paypal_transactions",
            description="Retrieve PayPal transaction history.",
            inputSchema={
                "type": "object",
                "properties": {
                    "days_back": {
                        "type": "integer",
                        "description": "Number of days of transaction history to retrieve",
                        "default": 30,
                    },
                    "max_results": {
                        "type": "integer",
                        "description": "Maximum number of transactions to return",
                        "default": 20,
                    },
                },
                "required": [],
            },
        ),
    ]


@app.call_tool()
async def call_tool(name: str, arguments: dict) -> list[TextContent]:
    """Execute tool by translating to HTTP request to mock service."""
    async with httpx.AsyncClient(timeout=30.0) as client:
        try:
            if name == "get_latest_emails":
                response = await client.post(
                    f"{MOCK_SERVICE_URL}/gmail/messages",
                    json=arguments,
                )
            elif name == "send_email":
                response = await client.post(
                    f"{MOCK_SERVICE_URL}/gmail/send",
                    json=arguments,
                )
            elif name == "get_paypal_transactions":
                response = await client.post(
                    f"{MOCK_SERVICE_URL}/finance/transactions",
                    json=arguments,
                )
            else:
                return [TextContent(type="text", text=json.dumps({"error": f"Unknown tool: {name}"}))]

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
