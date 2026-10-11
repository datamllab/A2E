"""MCP Server for code_editor service.

Provides tools for reading and writing files in the workspace.
Internally proxies to the HTTP mock service on localhost:9101.
"""

from mcp.server import Server
from mcp.server.stdio import stdio_server
from mcp.types import Tool
import httpx
import json

server = Server("code_editor")

PORT = 9101


@server.list_tools()
async def list_tools() -> list[Tool]:
    """Define available tools for the code editor."""
    return [
        Tool(
            name="read_file",
            description="Read the content of a file from the workspace. Provide the file path to read its contents.",
            inputSchema={
                "type": "object",
                "properties": {
                    "file_path": {
                        "type": "string",
                        "description": "Path to the file to read (e.g. 'legacy_code.txt')",
                    }
                },
                "required": ["file_path"],
            },
        ),
        Tool(
            name="write_file",
            description="Write content to a file in the workspace. Provide the file path and the content to write.",
            inputSchema={
                "type": "object",
                "properties": {
                    "file_path": {
                        "type": "string",
                        "description": "Path to the file to write (e.g. 'legacy_code_annotated.py')",
                    },
                    "content": {
                        "type": "string",
                        "description": "The content to write to the file",
                    },
                },
                "required": ["file_path", "content"],
            },
        ),
    ]


@server.call_tool()
async def call_tool(name: str, arguments: dict):
    """Proxy tool calls to the HTTP mock service."""
    url = f"http://localhost:{PORT}/code_editor/{name}"
    async with httpx.AsyncClient(timeout=30.0) as client:
        response = await client.post(url, json=arguments)
        return [response.text]


async def main():
    async with stdio_server() as (read_stream, write_stream):
        await server.run(read_stream, write_stream)


if __name__ == "__main__":
    import asyncio

    asyncio.run(main())
