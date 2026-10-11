#!/usr/bin/env python3
"""MCP Server for Banking - wraps HTTP mock service with tool schema."""

import asyncio
import json
import httpx
from mcp.server import Server
from mcp.server.stdio import stdio_server
from mcp.types import Tool, TextContent

# HTTP mock service endpoint
MOCK_SERVICE_URL = "http://localhost:9104"

app = Server("banking")


@app.list_tools()
async def list_tools() -> list[Tool]:
    """Define available tools with their schemas."""
    return [
        Tool(
            name="list_files",
            description="List available files in the banking system",
            inputSchema={
                "type": "object",
                "properties": {},
                "required": []
            }
        ),
        Tool(
            name="read_file",
            description="Read a file from the banking system. Example: read_file(file_path='adjuster-notes.txt') to read an adjuster notice",
            inputSchema={
                "type": "object",
                "properties": {
                    "file_path": {
                        "type": "string",
                        "description": "Name of the file to read (e.g. 'adjuster-notes.txt', 'claim-december-2023.txt', 'policy-update.txt')"
                    }
                },
                "required": ["file_path"]
            }
        ),
        Tool(
            name="get_scheduled_transactions",
            description="Get scheduled transactions",
            inputSchema={
                "type": "object",
                "properties": {},
                "required": []
            }
        ),
        Tool(
            name="update_scheduled_transaction",
            description="Update a scheduled transaction",
            inputSchema={
                "type": "object",
                "properties": {
                    "id": {
                        "type": "integer",
                        "description": "ID of the transaction to update"
                    },
                    "recipient": {
                        "type": "string",
                        "description": "IBAN of the recipient"
                    },
                    "amount": {
                        "type": "number",
                        "description": "Amount of the transaction"
                    },
                    "subject": {
                        "type": "string",
                        "description": "Subject of the transaction"
                    },
                    "date": {
                        "type": "string",
                        "description": "Date of the transaction"
                    },
                    "recurring": {
                        "type": "boolean",
                        "description": "Is the transaction recurring"
                    }
                },
                "required": ["id"]
            }
        )
    ]


@app.call_tool()
async def call_tool(name: str, arguments: dict) -> list[TextContent]:
    """Execute tool by translating to HTTP request to mock service."""
    async with httpx.AsyncClient(timeout=30.0) as client:
        try:
            if name == "list_files":
                response = await client.post(
                    f"{MOCK_SERVICE_URL}/banking/files/list",
                    json=arguments or {}
                )
                response.raise_for_status()
                result = response.json()
                return [TextContent(type="text", text=json.dumps(result, indent=2))]

            elif name == "read_file":
                response = await client.post(
                    f"{MOCK_SERVICE_URL}/banking/files/read",
                    json=arguments
                )
                response.raise_for_status()
                result = response.json()
                return [TextContent(type="text", text=json.dumps(result, indent=2))]

            elif name == "get_scheduled_transactions":
                response = await client.post(
                    f"{MOCK_SERVICE_URL}/banking/transactions/scheduled",
                    json=arguments
                )
                response.raise_for_status()
                result = response.json()
                return [TextContent(type="text", text=json.dumps(result, indent=2))]

            elif name == "update_scheduled_transaction":
                response = await client.post(
                    f"{MOCK_SERVICE_URL}/banking/transactions/scheduled/update",
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