"""MCP Server for File Storage Tools.

Wraps HTTP mock service (localhost:9133) with abstract tool definitions.
Agent sees tools as function calls, not HTTP APIs.

Tools: download_image
"""

import json
import httpx
from mcp.server import Server
from mcp.server.stdio import stdio_server
from mcp.types import Tool, TextContent

# Create MCP server instance
server = Server("file_storage")

# HTTP mock service base URL (internal - not exposed to agent)
HTTP_BASE_URL = "http://localhost:9133"

# Tool-to-endpoint mapping (internal)
TOOL_ENDPOINTS = {
    "download_image": "/file_storage/get",
}


@server.list_tools()
async def list_tools() -> list[Tool]:
    """Return tool definitions for File Storage."""
    return [
        Tool(
            name="download_image",
            description="Download an image from a URL or file path.",
            inputSchema={
                "type": "object",
                "properties": {
                    "file_id": {
                        "type": "string",
                        "description": "File ID or URL of the image to download"
                    }
                },
                "required": ["file_id"]
            }
        ),
    ]


@server.call_tool()
async def call_tool(name: str, arguments: dict) -> list[TextContent]:
    """Execute tool by calling HTTP endpoint internally."""
    if name not in TOOL_ENDPOINTS:
        return [TextContent(type="text", text=f"Unknown tool: {name}")]

    endpoint = TOOL_ENDPOINTS[name]
    url = f"{HTTP_BASE_URL}{endpoint}"

    try:
        with httpx.Client(timeout=30.0) as client:
            response = client.post(url, json=arguments)
            response.raise_for_status()
            result = response.json()

        return [TextContent(type="text", text=json.dumps(result, indent=2))]
    except httpx.HTTPError as e:
        return [TextContent(type="text", text=f"Error calling {name}: {str(e)}")]


async def main():
    """Run MCP server via stdio."""
    async with stdio_server() as (read_stream, write_stream):
        await server.run(read_stream, write_stream, server.create_initialization_options())


if __name__ == "__main__":
    import asyncio
    asyncio.run(main())