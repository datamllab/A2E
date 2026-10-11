"""MCP Server for HRM service.

Defines tool schema and translates tool calls to HTTP requests
to the mock service running on port 9100.
"""

from __future__ import annotations

import json
import os
import sys
from pathlib import Path

# Fix imports for bundled execution
sys.path.insert(0, str(Path(__file__).parent))

try:
    import httpx
    from mcp.server import Server
    from mcp.server.stdio import stdio_server
    from mcp.types import Tool, TextContent
except ImportError:
    print("MCP dependencies not available", file=sys.stderr)
    sys.exit(1)

# Service configuration
SERVICE_HOST = "localhost"
SERVICE_PORT = int(os.environ.get("HRM_SERVICE_PORT", "9100"))
SERVICE_BASE_URL = f"http://{SERVICE_HOST}:{SERVICE_PORT}/hrm"

server = Server("hrm_service")


@server.list_tools()
async def list_tools() -> list[Tool]:
    """Define available tools for the HRM service."""
    return [
        Tool(
            name="workplace_resolution_guide",
            description="A tool for facilitating workplace conflict resolution, guiding mediation processes, and documenting resolution outcomes to maintain a productive work environment.",
            inputSchema={
                "type": "object",
                "properties": {
                    "query": {
                        "type": "string",
                        "description": "Query parameter",
                    }
                },
                "required": ["query"],
            },
        ),
        Tool(
            name="employee_wellness_tracker",
            description="A tool for tracking employee wellness metrics, managing mental health resources, and monitoring workplace stress indicators to support employee wellbeing programs.",
            inputSchema={
                "type": "object",
                "properties": {
                    "query": {
                        "type": "string",
                        "description": "Query parameter",
                    }
                },
                "required": ["query"],
            },
        ),
        Tool(
            name="EmployeeDataRetrieval",
            description="Deploy the EmployeeDataRetrieval to access employee data securely, supporting HR research and organizational development initiatives.",
            inputSchema={
                "type": "object",
                "properties": {
                    "action": {
                        "type": "string",
                        "description": "Action to perform",
                    },
                    "target": {
                        "type": "string",
                        "description": "Target identifier",
                    },
                },
                "required": ["action"],
            },
        ),
    ]


@server.call_tool()
async def call_tool(name: str, arguments: dict) -> list[TextContent]:
    """Execute tool call by translating to HTTP request to mock service."""
    url = f"{SERVICE_BASE_URL}/{name}"

    try:
        async with httpx.AsyncClient() as client:
            response = await client.post(url, json=arguments, timeout=30.0)
            response.raise_for_status()
            result = response.json()
            return [TextContent(type="text", text=json.dumps(result, indent=2))]
    except httpx.HTTPError as e:
        return [TextContent(type="text", text=json.dumps({"error": str(e)}))]
    except Exception as e:
        return [TextContent(type="text", text=json.dumps({"error": f"Unexpected error: {e}"}))]


async def main():
    async with stdio_server() as (read_stream, write_stream):
        await server.run(read_stream, write_stream, server.create_initialization_options())


if __name__ == "__main__":
    import asyncio
    asyncio.run(main())