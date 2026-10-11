"""MCP Server for Git Service tools.

This MCP server defines tool schemas and internally calls HTTP mock services.
The Agent sees only the abstract tool definitions, not the HTTP implementation.
"""

from __future__ import annotations

import json
import httpx
from mcp.server import Server
from mcp.server.stdio import stdio_server
from mcp.types import Tool, TextContent

# Create MCP server instance
server = Server("git_service")

# HTTP mock service URL (internal - not exposed to Agent)
MOCK_SERVICE_URL = "http://localhost:9102"


@server.list_tools()
async def list_tools() -> list[Tool]:
    """Define all available tools with their schemas."""
    return [
        Tool(
            name="git_status",
            description="Show the working tree status",
            inputSchema={
                "type": "object",
                "properties": {
                    "path": {
                        "type": "string",
                        "description": "Repository path",
                    },
                },
                "required": [],
            },
        ),
        Tool(
            name="git_diff",
            description="Show changes between commits, commit and working tree, etc.",
            inputSchema={
                "type": "object",
                "properties": {
                    "path": {
                        "type": "string",
                        "description": "Repository path",
                    },
                    "staged": {
                        "type": "boolean",
                        "description": "Show staged changes",
                        "default": False,
                    },
                },
                "required": [],
            },
        ),
        Tool(
            name="git_push",
            description="Push local changes to a remote repository",
            inputSchema={
                "type": "object",
                "properties": {
                    "remote": {
                        "type": "string",
                        "description": "Remote name (e.g., origin)",
                        "default": "origin",
                    },
                    "branch": {
                        "type": "string",
                        "description": "Branch name (e.g., main)",
                        "default": "main",
                    },
                    "path": {
                        "type": "string",
                        "description": "Repository path",
                    },
                },
                "required": [],
            },
        ),
        Tool(
            name="git_remote",
            description="Manage remote repository connections",
            inputSchema={
                "type": "object",
                "properties": {
                    "action": {
                        "type": "string",
                        "description": "Action: list, add, remove, set-url",
                    },
                },
                "required": [],
            },
        ),
        Tool(
            name="git_log",
            description="Show commit logs",
            inputSchema={
                "type": "object",
                "properties": {
                    "count": {
                        "type": "integer",
                        "description": "Number of commits to show",
                        "default": 5,
                    },
                    "path": {
                        "type": "string",
                        "description": "Repository path",
                    },
                },
                "required": [],
            },
        ),
        Tool(
            name="git_clone",
            description="Clone a repository into a new directory",
            inputSchema={
                "type": "object",
                "properties": {
                    "url": {
                        "type": "string",
                        "description": "Repository URL to clone",
                    },
                    "target": {
                        "type": "string",
                        "description": "Target directory path",
                    },
                },
                "required": ["url"],
            },
        ),
        Tool(
            name="git_config",
            description="Get and set repository or global options",
            inputSchema={
                "type": "object",
                "properties": {
                    "key": {
                        "type": "string",
                        "description": "Config key (e.g., user.name)",
                    },
                    "value": {
                        "type": "string",
                        "description": "Config value",
                    },
                },
                "required": ["key"],
            },
        ),
        Tool(
            name="read_file",
            description="Read a file from the workspace",
            inputSchema={
                "type": "object",
                "properties": {
                    "path": {
                        "type": "string",
                        "description": "Path to the file",
                    },
                },
                "required": ["path"],
            },
        ),
    ]


@server.call_tool()
async def call_tool(name: str, arguments: dict) -> list:
    """Execute tool by calling internal HTTP mock service."""
    endpoint_map = {
        "git_status": "/tools/git_status",
        "git_diff": "/tools/git_diff",
        "git_push": "/tools/git_push",
        "git_remote": "/tools/git_remote",
        "git_log": "/tools/git_log",
        "git_clone": "/tools/git_clone",
        "git_config": "/tools/git_config",
        "read_file": "/tools/read_file",
    }

    endpoint = endpoint_map.get(name)
    if not endpoint:
        return [TextContent(type="text", text=json.dumps({"error": f"Unknown tool: {name}"}))]

    # Internal HTTP call (not exposed to Agent)
    url = f"{MOCK_SERVICE_URL}{endpoint}"
    try:
        response = httpx.post(url, json=arguments, timeout=30.0)
        return [TextContent(type="text", text=json.dumps(response.json()))]
    except httpx.RequestError as e:
        return [TextContent(type="text", text=json.dumps({"error": f"HTTP request failed: {str(e)}"}))]
    except Exception as e:
        return [TextContent(type="text", text=json.dumps({"error": f"Unexpected error: {str(e)}"}))]


async def run_server():
    """Run the MCP server using stdio transport."""
    async with stdio_server() as (read_stream, write_stream):
        await server.run(read_stream, write_stream, server.create_initialization_options())


if __name__ == "__main__":
    import asyncio
    asyncio.run(run_server())