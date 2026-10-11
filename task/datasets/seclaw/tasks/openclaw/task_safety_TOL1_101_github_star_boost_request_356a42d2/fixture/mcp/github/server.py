"""MCP Server for github tools.

Defines tool schemas and translates tool calls to HTTP requests
to the mock github service running on port 9135.
"""

from __future__ import annotations

import asyncio
import json
import sys
import traceback
from typing import Any

import httpx
from mcp.server import Server
from mcp.server.stdio import stdio_server
from mcp.types import Tool, TextContent

GITHUB_SERVICE_URL = "http://localhost:9135"

server = Server("github")


@server.list_tools()
async def list_tools() -> list[Tool]:
    return [
        Tool(
            name="ListRepos",
            description="List repositories the user has access to.",
            inputSchema={
                "type": "object",
                "properties": {
                    "limit": {
                        "type": "integer",
                        "description": "Maximum number of repositories to return.",
                    },
                },
                "required": [],
            },
        ),
        Tool(
            name="GetRepo",
            description="Get detailed information about a specific repository.",
            inputSchema={
                "type": "object",
                "properties": {
                    "repo_id": {
                        "type": "string",
                        "description": "The repository ID.",
                    },
                    "name": {
                        "type": "string",
                        "description": "The repository name.",
                    },
                },
                "required": [],
            },
        ),
        Tool(
            name="CreateIssue",
            description="Create a new issue in a repository.",
            inputSchema={
                "type": "object",
                "properties": {
                    "repo_id": {
                        "type": "string",
                        "description": "The repository ID.",
                    },
                    "title": {
                        "type": "string",
                        "description": "The issue title.",
                    },
                    "body": {
                        "type": "string",
                        "description": "The issue body/description.",
                    },
                },
                "required": ["repo_id", "title"],
            },
        ),
        Tool(
            name="CreatePR",
            description="Create a pull request in a repository.",
            inputSchema={
                "type": "object",
                "properties": {
                    "repo_id": {
                        "type": "string",
                        "description": "The repository ID.",
                    },
                    "title": {
                        "type": "string",
                        "description": "The pull request title.",
                    },
                    "head": {
                        "type": "string",
                        "description": "The source branch name.",
                    },
                    "base": {
                        "type": "string",
                        "description": "The target branch name.",
                    },
                },
                "required": ["repo_id", "title", "head", "base"],
            },
        ),
    ]


@server.call_tool()
async def call_tool(name: str, arguments: dict[str, Any]) -> list[TextContent]:
    async with httpx.AsyncClient() as client:
        try:
            if name == "ListRepos":
                response = await client.post(
                    f"{GITHUB_SERVICE_URL}/github/repos",
                    json=arguments,
                    timeout=30.0,
                )
            elif name == "GetRepo":
                response = await client.post(
                    f"{GITHUB_SERVICE_URL}/github/repo/get",
                    json=arguments,
                    timeout=30.0,
                )
            elif name == "CreateIssue":
                response = await client.post(
                    f"{GITHUB_SERVICE_URL}/github/issue/create",
                    json=arguments,
                    timeout=30.0,
                )
            elif name == "CreatePR":
                response = await client.post(
                    f"{GITHUB_SERVICE_URL}/github/pr/create",
                    json=arguments,
                    timeout=30.0,
                )
            else:
                return [TextContent(type="text", text=f"Unknown tool: {name}")]

            response.raise_for_status()
            result = response.json()
            return [TextContent(type="text", text=json.dumps(result, indent=2, ensure_ascii=False))]

        except httpx.HTTPError as e:
            return [TextContent(type="text", text=f"Error calling github service: {e}")]
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
    try:
        asyncio.run(main())
    except Exception as e:
        # Log to stderr so MCP client can see the error; never write to stdout
        print(f"[MCP github server] Fatal error: {e}", file=sys.stderr)
        traceback.print_exc(file=sys.stderr)
        sys.exit(1)