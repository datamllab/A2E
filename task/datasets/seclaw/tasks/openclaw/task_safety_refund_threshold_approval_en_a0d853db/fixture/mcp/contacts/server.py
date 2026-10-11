"""MCP server for contacts service."""

import json
import httpx
from mcp.server import Server
from mcp.server.stdio import stdio_server
from mcp.types import Tool, TextContent

SERVER_NAME = "contacts"
PORT = 9103
BASE_URL = f"http://localhost:{PORT}"

server = Server(SERVER_NAME)


@server.list_tools()
async def list_tools() -> list[Tool]:
    return [
        Tool(
            name="contacts_search",
            description="Search the contacts directory by name, department, or keyword",
            inputSchema={
                "type": "object",
                "properties": {
                    "query": {
                        "type": "string",
                        "description": "Search keyword (name, department, etc.)",
                    },
                    "department": {
                        "type": "string",
                        "description": "Filter by department",
                    },
                },
                "required": ["query"],
            },
        ),
        Tool(
            name="contacts_get",
            description="Get detailed contact information by contact ID",
            inputSchema={
                "type": "object",
                "properties": {
                    "contact_id": {
                        "type": "string",
                        "description": "Contact ID",
                    },
                },
                "required": ["contact_id"],
            },
        ),
    ]


@server.call_tool()
async def call_tool(name: str, arguments: dict):
    async with httpx.AsyncClient(timeout=30.0) as client:
        if name == "contacts_search":
            resp = await client.post(f"{BASE_URL}/contacts/search", json=arguments)
        elif name == "contacts_get":
            resp = await client.post(f"{BASE_URL}/contacts/get", json=arguments)
        else:
            return [TextContent(type="text", text=json.dumps({"error": f"Unknown tool: {name}"}))]

        return [TextContent(type="text", text=json.dumps(resp.json(), indent=2))]


async def main():
    async with stdio_server() as (read_stream, write_stream):
        await server.run(read_stream, write_stream, server.create_initialization_options())


if __name__ == "__main__":
    import asyncio
    asyncio.run(main())