"""MCP Server for file_storage service.

Defines tool schemas for Dropbox-like file operations and translates
MCP tool calls to HTTP requests to the file_storage mock service.
"""

import os
from mcp.server import Server
from mcp.server.stdio import stdio_server
from mcp.types import Tool
import httpx

# Mock service port (internal, not exposed to agent)
MOCK_PORT = os.environ.get("FILE_STORAGE_MOCK_PORT", "9133")
MOCK_BASE_URL = f"http://localhost:{MOCK_PORT}/file_storage"

server = Server("file_storage")


@server.list_tools()
async def list_tools() -> list[Tool]:
    """Return tool definitions for file_storage service."""
    return [
        Tool(
            name="ListFiles",
            description="List files and folders in Dropbox storage.",
            inputSchema={
                "type": "object",
                "properties": {
                    "path": {
                        "type": "string",
                        "description": "Folder path to list files from",
                    },
                },
                "required": [],
            },
        ),
        Tool(
            name="SearchFiles",
            description="Search for files in Dropbox storage by name or content.",
            inputSchema={
                "type": "object",
                "properties": {
                    "query": {
                        "type": "string",
                        "description": "Search query to find matching files",
                    },
                },
                "required": ["query"],
            },
        ),
        Tool(
            name="ShareFile",
            description="Create a share link for a file in Dropbox storage.",
            inputSchema={
                "type": "object",
                "properties": {
                    "file_id": {
                        "type": "string",
                        "description": "ID of the file to share",
                    },
                    "email": {
                        "type": "string",
                        "description": "Email address to share with",
                    },
                },
                "required": ["file_id", "email"],
            },
        ),
    ]


@server.call_tool()
async def call_tool(name: str, arguments: dict) -> list:
    """Translate MCP tool calls to HTTP requests to the mock service."""
    async with httpx.AsyncClient(timeout=30.0) as client:
        url = f"{MOCK_BASE_URL}/{name.lower()}"
        response = await client.post(url, json=arguments)
        return [response.json()]


async def main():
    """Run the MCP server."""
    async with stdio_server() as (read_stream, write_stream):
        await server.run(read_stream, write_stream, server.create_initialization_options())


if __name__ == "__main__":
    import asyncio
    asyncio.run(main())