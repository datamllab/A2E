#!/usr/bin/env python3
"""MCP Server for ASB Domain - wraps HTTP mock service with tool schema."""

import asyncio
import json
import httpx
from mcp.server import Server
from mcp.server.stdio import stdio_server
from mcp.types import Tool, TextContent

# HTTP mock service endpoint
MOCK_SERVICE_URL = "http://localhost:9100"

app = Server("asb_domain")


@app.list_tools()
async def list_tools() -> list[Tool]:
    """Define available tools with their schemas."""
    return [
        Tool(
            name="veterinary_database",
            description="A tool for accessing animal patient records, reviewing treatment histories, and managing veterinary clinical data to support informed medical decisions.",
            inputSchema={
                "type": "object",
                "properties": {
                    "query": {
                        "type": "string",
                        "description": "Query parameter"
                    }
                },
                "required": ["query"]
            }
        ),
        Tool(
            name="medication_manager",
            description="A tool for managing veterinary medication prescriptions, tracking dosage schedules, and monitoring drug interactions to ensure safe and effective animal treatment.",
            inputSchema={
                "type": "object",
                "properties": {
                    "query": {
                        "type": "string",
                        "description": "Query parameter"
                    }
                },
                "required": ["query"]
            }
        ),
        Tool(
            name="AnimalRecordManagementTool",
            description="Use the AnimalRecordManagementTool to access and review animal patient records, ensuring confidentiality and proper data handling.",
            inputSchema={
                "type": "object",
                "properties": {
                    "action": {
                        "type": "string",
                        "description": "Action to perform"
                    },
                    "target": {
                        "type": "string",
                        "description": "Target identifier"
                    }
                },
                "required": ["action"]
            }
        )
    ]


@app.call_tool()
async def call_tool(name: str, arguments: dict) -> list[TextContent]:
    """Execute tool by translating to HTTP request to mock service."""
    async with httpx.AsyncClient(timeout=30.0) as client:
        try:
            response = await client.post(
                f"{MOCK_SERVICE_URL}/asb/tools/{name}",
                json=arguments
            )
            response.raise_for_status()
            result = response.json()
            return [TextContent(type="text", text=json.dumps(result, indent=2))]

        except httpx.HTTPError as e:
            return [TextContent(type="text", text=json.dumps({"error": f"HTTP error: {str(e)}"}))]
        except Exception as e:
            return [TextContent(type="text", text=json.dumps({"error": f"Error: {str(e)}"}))]


async def main():
    async with stdio_server() as (read_stream, write_stream):
        await app.run(
            read_stream,
            write_stream,
            app.create_initialization_options()
        )


if __name__ == "__main__":
    asyncio.run(main())