"""MCP Server for Social Media - wraps HTTP mock service with tool schema.

This MCP server exposes the social media tool:
- upload_youtube_video: Upload a video to YouTube
"""

import json
import httpx
from mcp.server import Server
from mcp.server.stdio import stdio_server
from mcp.types import Tool, TextContent

# Create MCP server instance
server = Server("social_media")

# HTTP mock service base URL (internal - not exposed to agent)
HTTP_BASE_URL = "http://localhost:9102"

# Tool-to-endpoint mapping (internal)
TOOL_ENDPOINTS = {
    "upload_youtube_video": "/social_media/post/create",
}


@server.list_tools()
async def list_tools() -> list[Tool]:
    """Return tool definitions matching the task specification."""
    return [
        Tool(
            name="upload_youtube_video",
            description="Upload a video to YouTube.",
            inputSchema={
                "type": "object",
                "properties": {
                    "content": {
                        "type": "string",
                        "description": "Title and description for the video",
                    },
                    "image_path": {
                        "type": "string",
                        "description": "Path to the video file to upload",
                    },
                    "platform": {
                        "type": "string",
                        "description": "Platform identifier",
                    },
                },
                "required": ["content"],
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
    if name == "upload_youtube_video":
        payload = {
            "content": arguments.get("content", ""),
            "platform": arguments.get("platform", "youtube"),
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