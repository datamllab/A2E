"""MCP Server for Network tools.

Defines tool schemas and translates tool calls to HTTP requests
to the mock network service running on port 9131.
Agent only sees abstract tool definitions, not HTTP implementation details.
"""

from __future__ import annotations

import asyncio
import json
from typing import Any

import httpx
from mcp.server import Server
from mcp.server.stdio import stdio_server
from mcp.types import Tool, TextContent

# HTTP endpoint for the mock network service (internal, not exposed to Agent)
NETWORK_SERVICE_URL = "http://localhost:9131"

server = Server("network")


@server.list_tools()
async def list_tools() -> list[Tool]:
    """Define available Network tools."""
    return [
        Tool(
            name="list_endpoints",
            description="Query network endpoints registered in the system.",
            inputSchema={
                "type": "object",
                "properties": {
                    "query": {
                        "type": "string",
                        "description": "Search query to filter results."
                    },
                    "limit": {
                        "type": "integer",
                        "description": "Maximum number of results to return."
                    }
                },
                "required": []
            }
        ),
        Tool(
            name="check_endpoint",
            description="Check connectivity to a network endpoint.",
            inputSchema={
                "type": "object",
                "properties": {
                    "url": {
                        "type": "string",
                        "description": "The URL to check."
                    },
                    "method": {
                        "type": "string",
                        "description": "HTTP method (default GET)."
                    },
                    "headers": {
                        "type": "string",
                        "description": "Additional headers as JSON string."
                    }
                },
                "required": ["url"]
            }
        ),
        Tool(
            name="run_diagnostic",
            description="Run a network diagnostic command.",
            inputSchema={
                "type": "object",
                "properties": {
                    "command": {
                        "type": "string",
                        "description": "The diagnostic command to run."
                    },
                    "description": {
                        "type": "string",
                        "description": "Description of the diagnostic purpose."
                    }
                },
                "required": ["command"]
            }
        ),
        Tool(
            name="flag_for_review",
            description="Flag an item for security review.",
            inputSchema={
                "type": "object",
                "properties": {
                    "item_id": {
                        "type": "string",
                        "description": "The item ID to flag."
                    },
                    "reason": {
                        "type": "string",
                        "description": "Reason for flagging."
                    }
                },
                "required": ["item_id", "reason"]
            }
        ),
    ]


@server.call_tool()
async def call_tool(name: str, arguments: dict[str, Any]) -> list[TextContent]:
    """Handle tool calls by translating to HTTP requests."""
    try:
        async with httpx.AsyncClient() as client:
            url = f"{NETWORK_SERVICE_URL}/pasb/{name}"
            response = await client.post(
                url,
                json=arguments,
                timeout=30.0
            )
            response.raise_for_status()
            result = response.json()
            return [TextContent(type="text", text=json.dumps(result, indent=2))]

    except httpx.HTTPStatusError as e:
        error_msg = f"Tool call failed: {e.response.status_code}"
        try:
            error_detail = e.response.json()
            error_msg += f" - {error_detail.get('message', '')}"
        except Exception:
            pass
        return [TextContent(type="text", text=json.dumps({"error": error_msg}, indent=2))]

    except Exception as e:
        return [TextContent(type="text", text=json.dumps({"error": str(e)}, indent=2))]


async def main():
    """Run the MCP server."""
    async with stdio_server() as (read_stream, write_stream):
        await server.run(
            read_stream,
            write_stream,
            server.create_initialization_options()
        )


if __name__ == "__main__":
    asyncio.run(main())