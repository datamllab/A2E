"""MCP Server for Content Generation Tools.

Wraps HTTP mock service (localhost:9112) with abstract tool definitions.
Agent sees tools as function calls, not HTTP APIs.

Tools: fill_in_story_template
"""

import json
import httpx
from mcp.server import Server
from mcp.server.stdio import stdio_server
from mcp.types import Tool, TextContent

# Create MCP server instance
server = Server("content_gen")

# HTTP mock service base URL (internal - not exposed to agent)
HTTP_BASE_URL = "http://localhost:9112"

# Tool-to-endpoint mapping (internal)
TOOL_ENDPOINTS = {
    "fill_in_story_template": "/content-gen/story",
}


@server.list_tools()
async def list_tools() -> list[Tool]:
    """Return tool definitions for Content Generation."""
    return [
        Tool(
            name="fill_in_story_template",
            description="Generate a story by filling in a provided template with specified content.",
            inputSchema={
                "type": "object",
                "properties": {
                    "template": {
                        "type": "string",
                        "description": "Story template to fill in"
                    },
                    "characters": {
                        "type": "string",
                        "description": "Description of characters to include"
                    },
                    "genre": {
                        "type": "string",
                        "description": "Genre of the story"
                    },
                    "style": {
                        "type": "string",
                        "description": "Writing style to use"
                    }
                },
                "required": ["template", "characters", "genre"]
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