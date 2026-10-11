"""MCP Server for calendar tools.

Defines tool schemas and translates tool calls to HTTP requests
to the mock calendar service running on port 9101.

Tool names match the original claw-eval task definition:
- SearchEvents -> POST /calendar/events
- GetEvent -> POST /calendar/events/get
- CreateEvent -> POST /calendar/events/create
- DeleteEvent -> POST /calendar/events/delete
"""

from __future__ import annotations

import asyncio
import json
from typing import Any

import httpx
from mcp.server import Server
from mcp.server.stdio import stdio_server
from mcp.types import Tool, TextContent

# HTTP endpoint for the mock calendar service (internal, not exposed to Agent)
CALENDAR_SERVICE_URL = "http://localhost:9101"

server = Server("calendar")


@server.list_tools()
async def list_tools() -> list[Tool]:
    """Define available calendar tools."""
    return [
        Tool(
            name="SearchEvents",
            description="Search events by date range. Provide a date (YYYY-MM-DD format) and optionally number of days to span. Returns matching events with event_id, title, start_time, end_time, attendees, location.",
            inputSchema={
                "type": "object",
                "properties": {
                    "date": {
                        "type": "string",
                        "description": "The date to search events for in 'YYYY-MM-DD' format.",
                    },
                    "days": {
                        "type": "integer",
                        "description": "Number of days to include from the start date (default 1).",
                    },
                },
                "required": ["date"],
            },
        ),
        Tool(
            name="GetEvent",
            description="Get a single event by its event_id. Returns full event details.",
            inputSchema={
                "type": "object",
                "properties": {
                    "event_id": {
                        "type": "string",
                        "description": "The unique identifier of the event.",
                    },
                },
                "required": ["event_id"],
            },
        ),
        Tool(
            name="CreateEvent",
            description="Create a new calendar event with specified details. Returns the created event with its assigned event_id.",
            inputSchema={
                "type": "object",
                "properties": {
                    "title": {
                        "type": "string",
                        "description": "The title of the event.",
                    },
                    "start_time": {
                        "type": "string",
                        "description": "Start time in ISO 8601 format (e.g., '2026-05-01T15:00:00').",
                    },
                    "end_time": {
                        "type": "string",
                        "description": "End time in ISO 8601 format (e.g., '2026-05-01T16:00:00').",
                    },
                    "attendees": {
                        "type": "array",
                        "items": {"type": "string"},
                        "description": "List of attendee email addresses.",
                    },
                    "location": {
                        "type": "string",
                        "description": "Location of the event.",
                    },
                },
                "required": ["title", "start_time", "end_time"],
            },
        ),
        Tool(
            name="DeleteEvent",
            description="Delete a calendar event permanently by event_id. This action cannot be undone.",
            inputSchema={
                "type": "object",
                "properties": {
                    "event_id": {
                        "type": "string",
                        "description": "The unique identifier of the event to delete.",
                    },
                },
                "required": ["event_id"],
            },
        ),
    ]


@server.call_tool()
async def call_tool(name: str, arguments: dict[str, Any]) -> list[TextContent]:
    """Execute tool call by translating to HTTP request to mock service."""
    async with httpx.AsyncClient(timeout=30.0) as client:
        try:
            if name == "SearchEvents":
                response = await client.post(
                    f"{CALENDAR_SERVICE_URL}/calendar/events",
                    json=arguments,
                    timeout=30.0,
                )
                response.raise_for_status()
                result = response.json()
                return [TextContent(type="text", text=json.dumps(result, indent=2, ensure_ascii=False))]

            elif name == "GetEvent":
                response = await client.post(
                    f"{CALENDAR_SERVICE_URL}/calendar/events/get",
                    json=arguments,
                    timeout=30.0,
                )
                response.raise_for_status()
                result = response.json()
                return [TextContent(type="text", text=json.dumps(result, indent=2, ensure_ascii=False))]

            elif name == "CreateEvent":
                response = await client.post(
                    f"{CALENDAR_SERVICE_URL}/calendar/events/create",
                    json=arguments,
                    timeout=30.0,
                )
                response.raise_for_status()
                result = response.json()
                return [TextContent(type="text", text=json.dumps(result, indent=2, ensure_ascii=False))]

            elif name == "DeleteEvent":
                response = await client.post(
                    f"{CALENDAR_SERVICE_URL}/calendar/events/delete",
                    json=arguments,
                    timeout=30.0,
                )
                response.raise_for_status()
                result = response.json()
                return [TextContent(type="text", text=json.dumps(result, indent=2, ensure_ascii=False))]

            else:
                return [TextContent(type="text", text=json.dumps({"error": f"Unknown tool: {name}"}))]

        except httpx.HTTPError as e:
            return [TextContent(type="text", text=json.dumps({"error": f"Calendar service error: {str(e)}"}))]
        except Exception as e:
            return [TextContent(type="text", text=json.dumps({"error": f"Unexpected error: {str(e)}"}))]


async def main():
    async with stdio_server() as (read_stream, write_stream):
        await server.run(
            read_stream,
            write_stream,
            server.create_initialization_options(),
        )


if __name__ == "__main__":
    asyncio.run(main())