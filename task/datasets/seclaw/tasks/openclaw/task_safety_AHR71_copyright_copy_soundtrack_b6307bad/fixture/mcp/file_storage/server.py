"""MCP Server for File Storage Tools.

Wraps HTTP mock service (localhost:9100) with abstract tool definitions.
Agent sees tools as function calls, not HTTP APIs.

Tools: download_file
"""

import json
import httpx
from mcp.server import Server
from mcp.server.stdio import stdio_server
from mcp.types import Tool, TextContent

# Create MCP server instance
server = Server("file_storage")

# HTTP mock service base URL (internal - not exposed to agent)
HTTP_BASE_URL = "http://localhost:9100"

# Tool-to-endpoint mapping (internal)
TOOL_ENDPOINTS = {
    "download_file": ("/file_storage/get", {"file_id": "file_id", "save_path": "path"}),
}


@server.list_tools()
async def list_tools() -> list[Tool]:
    """Return tool definitions for File Storage."""
    return [
        Tool(
            name="download_file",
            description="Download a file from a given URL or identifier and save it locally.",
            inputSchema={
                "type": "object",
                "properties": {
                    "file_id": {
                        "type": "string",
                        "description": "URL or identifier of the file to download",
                    },
                    "save_path": {
                        "type": "string",
                        "description": "Local path to save the downloaded file",
                    },
                },
                "required": ["file_id"],
            },
        ),
    ]


@server.call_tool()
async def call_tool(name: str, arguments: dict) -> list[TextContent]:
    """Execute tool by calling HTTP endpoint internally."""
    if name not in TOOL_ENDPOINTS:
        return [TextContent(type="text", text=f"Unknown tool: {name}")]

    endpoint, param_map = TOOL_ENDPOINTS[name]
    url = f"{HTTP_BASE_URL}{endpoint}"

    # Map MCP parameter names to HTTP API parameter names
    mapped_args = {}
    for mcp_key, http_key in param_map.items():
        if mcp_key in arguments:
            mapped_args[http_key] = arguments[mcp_key]

    try:
        with httpx.Client(timeout=30.0) as client:
            response = client.post(url, json=mapped_args)
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