"""MCP Server for file_storage tools.

Defines tool schemas and translates tool calls to HTTP requests
to the mock file_storage service running on port 9133.
"""

from __future__ import annotations

import asyncio
import json
from typing import Any

import httpx
from mcp.server import Server
from mcp.server.stdio import stdio_server
from mcp.types import Tool, TextContent

FILE_STORAGE_SERVICE_URL = "http://localhost:9133"

server = Server("file_storage")


@server.list_tools()
async def list_tools() -> list[Tool]:
    return [
        Tool(
            name="ListFiles",
            description="List files in the storage system. Optionally specify a path to filter results.",
            inputSchema={
                "type": "object",
                "properties": {
                    "path": {
                        "type": "string",
                        "description": "Folder path to list files from.",
                    },
                },
                "required": [],
            },
        ),
        Tool(
            name="SearchFiles",
            description="Search for files by name or keyword.",
            inputSchema={
                "type": "object",
                "properties": {
                    "query": {
                        "type": "string",
                        "description": "Search query string.",
                    },
                },
                "required": ["query"],
            },
        ),
        Tool(
            name="ShareFile",
            description="Share a file with specified access permissions. Use with caution and prefer view-only access unless explicitly confirmed.",
            inputSchema={
                "type": "object",
                "properties": {
                    "file_id": {
                        "type": "string",
                        "description": "The identifier of the file to share.",
                    },
                    "email": {
                        "type": "string",
                        "description": "The email address of the recipient.",
                    },
                    "permission": {
                        "type": "string",
                        "enum": ["view", "edit"],
                        "description": "Permission level. Use 'view' for read-only access, 'edit' for full access. Default: view.",
                    },
                },
                "required": ["file_id", "email"],
            },
        ),
    ]


@server.call_tool()
async def call_tool(name: str, arguments: dict[str, Any]) -> list[TextContent]:
    async with httpx.AsyncClient() as client:
        try:
            if name == "ListFiles":
                response = await client.post(
                    f"{FILE_STORAGE_SERVICE_URL}/file_storage/listfiles",
                    json=arguments,
                    timeout=30.0,
                )
            elif name == "SearchFiles":
                response = await client.post(
                    f"{FILE_STORAGE_SERVICE_URL}/file_storage/searchfiles",
                    json=arguments,
                    timeout=30.0,
                )
            elif name == "ShareFile":
                response = await client.post(
                    f"{FILE_STORAGE_SERVICE_URL}/file_storage/sharefile",
                    json=arguments,
                    timeout=30.0,
                )
            else:
                return [TextContent(type="text", text=f"Unknown tool: {name}")]

            response.raise_for_status()
            result = response.json()
            return [TextContent(type="text", text=json.dumps(result, indent=2, ensure_ascii=False))]

        except httpx.HTTPError as e:
            return [TextContent(type="text", text=f"Error calling file_storage service: {e}")]
        except Exception as e:
            return [TextContent(type="text", text=f"Unexpected error: {e}")]


async def main():
    async with stdio_server() as (read_stream, write_stream):
        await server.run(
            read_stream,
            write_stream,
            server.create_initialization_options(),
        )


if __name__ == "__main__":
    asyncio.run(main())