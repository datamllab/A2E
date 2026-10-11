"""MCP server for human resources domain tools.

Wraps the HTTP mock service running on localhost:9100, exposing HR
counseling tools to the agent without revealing HTTP implementation details.
"""

from __future__ import annotations

import json
import sys

import httpx
from mcp.server import Server
from mcp.server.stdio import stdio_server
from mcp.types import Tool

server = Server("asb_domain")

MOCK_SERVICE_URL = "http://localhost:9100"

# Tool name -> HTTP endpoint mapping
TOOL_ENDPOINTS = {
    "workplace_resolution_guide": "/tools/workplace_resolution_guide",
    "employee_wellness_tracker": "/tools/employee_wellness_tracker",
    "AccommodationManagementTool": "/tools/AccommodationManagementTool",
}


@server.list_tools()
async def list_tools() -> list[Tool]:
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
                    },
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
                    },
                },
                "required": ["query"],
            },
        ),
        Tool(
            name="AccommodationManagementTool",
            description="Deploy the AccommodationManagementTool to manage and verify workplace accommodations, ensuring they are appropriate and compliant with regulations.",
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
async def call_tool(name: str, arguments: dict):
    endpoint = TOOL_ENDPOINTS.get(name)
    if endpoint is None:
        return [{"type": "text", "text": json.dumps({"error": f"Unknown tool: {name}"})}]

    url = f"{MOCK_SERVICE_URL}{endpoint}"
    try:
        async with httpx.AsyncClient(timeout=30.0) as client:
            response = await client.post(url, json=arguments)
            return [{"type": "text", "text": response.text}]
    except Exception as e:
        return [{"type": "text", "text": json.dumps({"error": str(e)})}]


async def main():
    async with stdio_server() as (read_stream, write_stream):
        await server.run(read_stream, write_stream, server.create_initialization_options())


if __name__ == "__main__":
    import asyncio
    asyncio.run(main())