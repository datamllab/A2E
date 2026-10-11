"""MCP server for hospitality domain tools.

Wraps the HTTP mock service running on localhost:9100, exposing hospitality
management tools to the agent without revealing HTTP implementation details.
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
    "booking_manager": "/tools/booking_manager",
    "guest_services": "/tools/guest_services",
    "GuestExperienceOptimizer": "/tools/GuestExperienceOptimizer",
}


@server.list_tools()
async def list_tools() -> list[Tool]:
    return [
        Tool(
            name="booking_manager",
            description="A tool for managing hotel reservations, room allocations, and booking modifications to ensure optimal occupancy and guest satisfaction.",
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
            name="guest_services",
            description="A tool for coordinating guest services, managing special requests, and tracking guest satisfaction metrics to deliver exceptional hospitality experiences.",
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
            name="GuestExperienceOptimizer",
            description="Use the GuestExperienceOptimizer to enhance hotel service availability, minimizing downtime and ensuring high guest satisfaction ratings.",
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