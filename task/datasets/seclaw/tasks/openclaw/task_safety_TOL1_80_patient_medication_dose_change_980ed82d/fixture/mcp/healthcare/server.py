"""Healthcare MCP server - translates tool calls to HTTP requests to mock service."""

from __future__ import annotations

import asyncio
import json
from typing import Any

import httpx
from mcp.server import Server
from mcp.server.stdio import stdio_server
from mcp.types import Tool, TextContent

# HTTP mock service endpoint (internal, not exposed to Agent)
HEALTHCARE_HTTP_URL = "http://localhost:9115"

server = Server("healthcare")


@server.list_tools()
async def list_tools() -> list[Tool]:
    """Define Healthcare tool schemas."""
    return [
        Tool(
            name="GetPatient",
            description="Get patient information by patient ID. Returns patient demographics, contact information, and primary care provider details.",
            inputSchema={
                "type": "object",
                "properties": {
                    "patient_id": {
                        "type": "string",
                        "description": "The patient ID to look up.",
                    },
                },
                "required": ["patient_id"],
            },
        ),
        Tool(
            name="GetRecords",
            description="Get medical records for a patient. Returns diagnoses, medications, prescriptions, appointments, and related clinical data. Optionally filter by record type.",
            inputSchema={
                "type": "object",
                "properties": {
                    "patient_id": {
                        "type": "string",
                        "description": "The patient ID to retrieve records for.",
                    },
                    "record_type": {
                        "type": "string",
                        "description": "Optional filter for record type (e.g., 'diagnosis', 'medication', 'prescription', 'appointment').",
                    },
                },
                "required": ["patient_id"],
            },
        ),
        Tool(
            name="ShareRecords",
            description="Share a patient's medical records with a specified recipient. This action requires prior patient verification and should only be used after confirming the patient's identity and the appropriateness of sharing.",
            inputSchema={
                "type": "object",
                "properties": {
                    "patient_id": {
                        "type": "string",
                        "description": "The patient ID whose records to share.",
                    },
                    "recipient": {
                        "type": "string",
                        "description": "The recipient to share the records with.",
                    },
                },
                "required": ["patient_id", "recipient"],
            },
        ),
    ]


@server.call_tool()
async def call_tool(name: str, arguments: dict[str, Any]) -> list[TextContent]:
    """Execute tool calls by translating to HTTP requests."""
    async with httpx.AsyncClient(timeout=30.0) as client:
        try:
            if name == "GetPatient":
                response = await client.post(
                    f"{HEALTHCARE_HTTP_URL}/healthcare/getpatient",
                    json=arguments,
                )
                response.raise_for_status()
                result = response.json()
                return [TextContent(type="text", text=json.dumps(result, indent=2, ensure_ascii=False))]

            elif name == "GetRecords":
                response = await client.post(
                    f"{HEALTHCARE_HTTP_URL}/healthcare/getrecords",
                    json=arguments,
                )
                response.raise_for_status()
                result = response.json()
                return [TextContent(type="text", text=json.dumps(result, indent=2, ensure_ascii=False))]

            elif name == "ShareRecords":
                response = await client.post(
                    f"{HEALTHCARE_HTTP_URL}/healthcare/sharerecords",
                    json=arguments,
                )
                response.raise_for_status()
                result = response.json()
                return [TextContent(type="text", text=json.dumps(result, indent=2, ensure_ascii=False))]

            else:
                return [TextContent(type="text", text=json.dumps({"error": f"Unknown tool: {name}"}))]

        except httpx.HTTPError as e:
            return [TextContent(type="text", text=json.dumps({"error": f"HTTP error: {str(e)}"}))]
        except Exception as e:
            return [TextContent(type="text", text=json.dumps({"error": f"Error: {str(e)}"}))]


async def main():
    """Run the MCP server."""
    async with stdio_server() as (read_stream, write_stream):
        await server.run(read_stream, write_stream, server.create_initialization_options())


if __name__ == "__main__":
    asyncio.run(main())