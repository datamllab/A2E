"""MCP Server for Travel Booking Tools.

Wraps HTTP mock service (localhost:9130) with abstract tool definitions.
Agent sees tools as function calls, not HTTP APIs.

Tools: GetHotelsPrices, GetHotelsAddress, GetRatingReviewsForHotels,
       ReserveHotel, GetAllCarRentalCompaniesInCity, GetCarFuelOptions,
       CreateCalendarEvent
"""

import json
import httpx
from mcp.server import Server
from mcp.server.stdio import stdio_server
from mcp.types import Tool, TextContent

# Create MCP server instance
server = Server("travel_booking")

# HTTP mock service base URL (internal - not exposed to agent)
HTTP_BASE_URL = "http://localhost:9130"

# Tool-to-endpoint mapping (internal)
TOOL_ENDPOINTS = {
    "GetHotelsPrices": ("/travel/hotels/prices", ["hotel_names"]),
    "GetHotelsAddress": ("/travel/hotels/address", ["hotel_name"]),
    "GetRatingReviewsForHotels": ("/travel/hotels/reviews", ["hotel_names"]),
    "ReserveHotel": ("/travel/hotels/reserve", ["hotel_name", "check_in", "check_out", "guests"]),
    "GetAllCarRentalCompaniesInCity": ("/travel/cars/companies", ["city"]),
    "GetCarFuelOptions": ("/travel/cars/fuel_options", ["company_name"]),
    "CreateCalendarEvent": ("/travel/calendar/create", ["title", "start_time", "end_time", "location"]),
}


@server.list_tools()
async def list_tools() -> list[Tool]:
    """Return tool definitions matching eventplan_usertask13."""
    return [
        Tool(
            name="GetHotelsPrices",
            description="Get price information for one or more hotels.",
            inputSchema={
                "type": "object",
                "properties": {
                    "hotel_names": {
                        "type": "array",
                        "items": {"type": "string"},
                        "description": "List of hotel names to get prices for.",
                    },
                },
                "required": ["hotel_names"],
            },
        ),
        Tool(
            name="GetHotelsAddress",
            description="Get the address of a specific hotel.",
            inputSchema={
                "type": "object",
                "properties": {
                    "hotel_name": {
                        "type": "string",
                        "description": "The name of the hotel.",
                    },
                },
                "required": ["hotel_name"],
            },
        ),
        Tool(
            name="GetRatingReviewsForHotels",
            description="Get rating and reviews for one or more hotels.",
            inputSchema={
                "type": "object",
                "properties": {
                    "hotel_names": {
                        "type": "array",
                        "items": {"type": "string"},
                        "description": "List of hotel names to get ratings and reviews for.",
                    },
                },
                "required": ["hotel_names"],
            },
        ),
        Tool(
            name="ReserveHotel",
            description="Reserve a hotel room.",
            inputSchema={
                "type": "object",
                "properties": {
                    "hotel_name": {
                        "type": "string",
                        "description": "The name of the hotel to reserve.",
                    },
                    "check_in": {
                        "type": "string",
                        "description": "Check-in date in YYYY-MM-DD format.",
                    },
                    "check_out": {
                        "type": "string",
                        "description": "Check-out date in YYYY-MM-DD format.",
                    },
                    "guests": {
                        "type": "integer",
                        "description": "Number of guests.",
                    },
                },
                "required": ["hotel_name"],
            },
        ),
        Tool(
            name="GetAllCarRentalCompaniesInCity",
            description="Get all car rental companies in a specific city.",
            inputSchema={
                "type": "object",
                "properties": {
                    "city": {
                        "type": "string",
                        "description": "The city to search for car rental companies.",
                    },
                },
                "required": ["city"],
            },
        ),
        Tool(
            name="GetCarFuelOptions",
            description="Get available fuel options for a specific car rental company.",
            inputSchema={
                "type": "object",
                "properties": {
                    "company_name": {
                        "type": "string",
                        "description": "The name of the car rental company.",
                    },
                },
                "required": ["company_name"],
            },
        ),
        Tool(
            name="CreateCalendarEvent",
            description="Create a new calendar event.",
            inputSchema={
                "type": "object",
                "properties": {
                    "title": {
                        "type": "string",
                        "description": "The title of the event.",
                    },
                    "start_time": {
                        "type": "string",
                        "description": "Start time of the event.",
                    },
                    "end_time": {
                        "type": "string",
                        "description": "End time of the event.",
                    },
                    "location": {
                        "type": "string",
                        "description": "Location of the event (optional).",
                    },
                },
                "required": ["title", "start_time", "end_time"],
            },
        ),
    ]


@server.call_tool()
async def call_tool(name: str, arguments: dict) -> list[TextContent]:
    """Execute tool by calling HTTP endpoint internally."""
    if name not in TOOL_ENDPOINTS:
        return [TextContent(type="text", text=f"Unknown tool: {name}")]

    endpoint, _ = TOOL_ENDPOINTS[name]
    url = f"{HTTP_BASE_URL}{endpoint}"

    try:
        # Make HTTP POST request internally
        with httpx.Client(timeout=30.0) as client:
            response = client.post(url, json=arguments)
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