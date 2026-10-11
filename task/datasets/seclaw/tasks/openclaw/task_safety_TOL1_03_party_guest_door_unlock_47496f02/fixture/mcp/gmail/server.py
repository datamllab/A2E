#!/usr/bin/env python3
"""MCP Server for Gmail - wraps HTTP mock service with tool schema."""

import asyncio
import json
import httpx
from mcp.server import Server
from mcp.server.stdio import stdio_server
from mcp.types import Tool, TextContent

# HTTP mock service endpoint
MOCK_SERVICE_URL = "http://localhost:9101"

app = Server("gmail")


@app.list_tools()
async def list_tools() -> list[Tool]:
    """Define available tools with their schemas."""
    return [
        Tool(
            name="SearchEmails",
            description="Searches emails by various criteria. Returns a list of emails with message_id, from, subject, date, is_read, and labels.",
            inputSchema={
                "type": "object",
                "properties": {
                    "days_back": {
                        "type": "integer",
                        "description": "Number of days back to search (default 7)."
                    },
                    "max_results": {
                        "type": "integer",
                        "description": "Maximum number of results to return (default 20)."
                    }
                },
                "required": []
            }
        ),
        Tool(
            name="GetEmail",
            description="Gets a single email by message_id. Returns full email content including body.",
            inputSchema={
                "type": "object",
                "properties": {
                    "message_id": {
                        "type": "string",
                        "description": "The message ID to retrieve."
                    }
                },
                "required": ["message_id"]
            }
        ),
    ]


@app.call_tool()
async def call_tool(name: str, arguments: dict) -> list[TextContent]:
    """Execute tool by translating to HTTP request to mock service."""
    async with httpx.AsyncClient(timeout=30.0) as client:
        try:
            if name == "SearchEmails":
                response = await client.post(
                    f"{MOCK_SERVICE_URL}/gmail/messages",
                    json=arguments
                )
                response.raise_for_status()
                result = response.json()
                return [TextContent(type="text", text=json.dumps(result, indent=2))]

            elif name == "GetEmail":
                response = await client.post(
                    f"{MOCK_SERVICE_URL}/gmail/messages/get",
                    json=arguments
                )
                response.raise_for_status()
                result = response.json()
                return [TextContent(type="text", text=json.dumps(result, indent=2))]

            else:
                return [TextContent(type="text", text=json.dumps({"error": f"Unknown tool: {name}"}))]

        except httpx.HTTPError as e:
            return [TextContent(type="text", text=json.dumps({"error": f"HTTP error: {str(e)}"}))]
        except Exception as e:
            return [TextContent(type="text", text=json.dumps({"error": f"Error: {str(e)}"}))]


async def main():
    async with stdio_server() as (read_stream, write_stream):
        await app.run(
            read_stream,
            write_stream,
            app.create_initialization_options()
        )


if __name__ == "__main__":
    asyncio.run(main())