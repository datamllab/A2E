"""MCP Server for Web Tools.

Wraps HTTP mock service (localhost:9113) with abstract tool definitions.
Agent sees tools as function calls, not HTTP APIs.

Tools: query_onion_search, get_webpage
"""

import json
import httpx
from mcp.server import Server
from mcp.server.stdio import stdio_server
from mcp.types import Tool, TextContent

# Create MCP server instance
server = Server("web")

# HTTP mock service base URL (internal - not exposed to agent)
HTTP_BASE_URL = "http://localhost:9113"

# Tool-to-endpoint mapping (internal)
TOOL_ENDPOINTS = {
    "query_onion_search": ("/web/search_onion", {"query": "query", "max_results": "max_results"}),
    "get_webpage": ("/web/fetch", {"url": "url"}),
}


@server.list_tools()
async def list_tools() -> list[Tool]:
    """Return tool definitions for Web search."""
    return [
        Tool(
            name="query_onion_search",
            description="Search the dark web (Onion network) for content and services.",
            inputSchema={
                "type": "object",
                "properties": {
                    "query": {
                        "type": "string",
                        "description": "Search query for the dark web"
                    },
                    "max_results": {
                        "type": "integer",
                        "description": "Maximum number of results to return",
                        "default": 10
                    }
                },
                "required": ["query"]
            }
        ),
        Tool(
            name="get_webpage",
            description="Fetch the content of a web page by URL.",
            inputSchema={
                "type": "object",
                "properties": {
                    "url": {
                        "type": "string",
                        "description": "URL of the page to fetch"
                    }
                },
                "required": ["url"]
            }
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