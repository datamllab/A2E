"""Gmail MCP server - translates tool calls to HTTP requests."""

from mcp.server import Server
from mcp.server.stdio import stdio_server
from mcp.types import Tool, TextContent
import httpx
import json

server = Server("gmail")

MOCK_PORT = 9100

@server.list_tools()
async def list_tools() -> list[Tool]:
    """Define Gmail tool schemas."""
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
                        "default": 7
                    },
                    "max_results": {
                        "type": "integer",
                        "description": "Maximum number of results to return (default 20).",
                        "default": 20
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

@server.call_tool()
async def call_tool(name: str, arguments: dict) -> list:
    """Execute tool calls by translating to HTTP requests."""
    # Internal HTTP calls - not exposed to Agent
    base_url = f"http://localhost:{MOCK_PORT}"

    if name == "SearchEmails":
        response = httpx.post(f"{base_url}/gmail/messages", json=arguments)
        return [TextContent(type="text", text=json.dumps(response.json()))]

    if name == "GetEmail":
        response = httpx.post(f"{base_url}/gmail/messages/get", json=arguments)
        return [TextContent(type="text", text=json.dumps(response.json()))]

    return [TextContent(type="text", text=json.dumps({"error": f"Unknown tool: {name}"}))]

async def run():
    """Run the MCP server."""
    async with stdio_server() as (read_stream, write_stream):
        await server.run(read_stream, write_stream, server.create_initialization_options())

if __name__ == "__main__":
    import asyncio
    asyncio.run(run())