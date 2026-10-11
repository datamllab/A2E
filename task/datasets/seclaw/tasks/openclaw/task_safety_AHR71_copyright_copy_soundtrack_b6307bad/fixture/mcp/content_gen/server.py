"""MCP Server for Content Generation - wraps HTTP mock service with tool schema.

This MCP server exposes the content generation tool:
- create_ai_video: Generate a video using an AI video model
"""

import json
import httpx
from mcp.server import Server
from mcp.server.stdio import stdio_server
from mcp.types import Tool, TextContent

# Create MCP server instance
server = Server("content_gen")

# HTTP mock service base URL (internal - not exposed to agent)
HTTP_BASE_URL = "http://localhost:9101"

# Tool-to-endpoint mapping (internal)
TOOL_ENDPOINTS = {
    "create_ai_video": "/content-gen/video",
}


@server.list_tools()
async def list_tools() -> list[Tool]:
    """Return tool definitions matching the task specification."""
    return [
        Tool(
            name="create_ai_video",
            description="Generate a video using an AI video model.",
            inputSchema={
                "type": "object",
                "properties": {
                    "prompt": {
                        "type": "string",
                        "description": "Text prompt or description for the video",
                    },
                    "output_path": {
                        "type": "string",
                        "description": "Path to save the generated video",
                    },
                    "image_path": {
                        "type": "string",
                        "description": "Path to a source image for the video",
                    },
                },
                "required": ["prompt", "output_path"],
            },
        ),
    ]


@server.call_tool()
async def call_tool(name: str, arguments: dict) -> list[TextContent]:
    """Execute tool by calling HTTP endpoint internally."""
    if name not in TOOL_ENDPOINTS:
        return [TextContent(type="text", text=f"Unknown tool: {name}")]

    endpoint = TOOL_ENDPOINTS[name]
    url = f"{HTTP_BASE_URL}{endpoint}"

    # Map tool parameters to service parameters
    if name == "create_ai_video":
        payload = {
            "prompt": arguments.get("prompt", ""),
            "output_path": arguments.get("output_path", ""),
        }
        if arguments.get("image_path"):
            payload["image_path"] = arguments["image_path"]
    else:
        payload = arguments

    try:
        with httpx.Client(timeout=30.0) as client:
            response = client.post(url, json=payload)
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