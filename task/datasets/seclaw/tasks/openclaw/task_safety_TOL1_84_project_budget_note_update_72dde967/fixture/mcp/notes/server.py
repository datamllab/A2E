"""MCP Server for Notes Tools.

Wraps HTTP mock service (localhost:9111) with abstract tool definitions.
Agent sees tools as function calls, not HTTP APIs.

Tools: ListNotes, GetNote, CreateNote, SearchNotes
"""

import json
import httpx
from mcp.server import Server
from mcp.server.stdio import stdio_server
from mcp.types import Tool, TextContent

# Create MCP server instance
server = Server("notes")

# HTTP mock service base URL (internal - not exposed to agent)
HTTP_BASE_URL = "http://localhost:9111"

# Tool-to-endpoint mapping (internal)
TOOL_ENDPOINTS = {
    "ListNotes": "/notes/listnotes",
    "GetNote": "/notes/getnote",
    "CreateNote": "/notes/createnote",
    "SearchNotes": "/notes/searchnotes",
}


@server.list_tools()
async def list_tools() -> list[Tool]:
    """Return tool definitions matching claw-eval source."""
    return [
        Tool(
            name="ListNotes",
            description="List notes in the notebook. Returns note IDs, titles, and creation dates.",
            inputSchema={
                "type": "object",
                "properties": {
                    "limit": {
                        "type": "integer",
                        "description": "The limit."
                    }
                },
                "required": []
            }
        ),
        Tool(
            name="GetNote",
            description="Get detailed information about a specific note by its ID.",
            inputSchema={
                "type": "object",
                "properties": {
                    "note_id": {
                        "type": "string",
                        "description": "The note_id."
                    }
                },
                "required": ["note_id"]
            }
        ),
        Tool(
            name="CreateNote",
            description="Create a new note with a title and content.",
            inputSchema={
                "type": "object",
                "properties": {
                    "title": {
                        "type": "string",
                        "description": "The title."
                    },
                    "content": {
                        "type": "string",
                        "description": "The content."
                    }
                },
                "required": ["title", "content"]
            }
        ),
        Tool(
            name="SearchNotes",
            description="Search for notes by keyword in titles and content.",
            inputSchema={
                "type": "object",
                "properties": {
                    "query": {
                        "type": "string",
                        "description": "The query."
                    }
                },
                "required": ["query"]
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
        # Make HTTP POST request internally
        with httpx.Client(timeout=30.0) as client:
            response = client.post(url, json=arguments)
            response.raise_for_status()
            result = response.json()

        return [TextContent(type="text", text=json.dumps(result, indent=2, ensure_ascii=False))]
    except httpx.HTTPError as e:
        return [TextContent(type="text", text=f"Error calling {name}: {str(e)}")]


async def main():
    """Run MCP server via stdio."""
    async with stdio_server() as (read_stream, write_stream):
        await server.run(read_stream, write_stream, server.create_initialization_options())


if __name__ == "__main__":
    import asyncio
    asyncio.run(main())