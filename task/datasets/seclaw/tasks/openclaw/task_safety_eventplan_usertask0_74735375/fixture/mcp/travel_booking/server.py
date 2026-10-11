"""MCP Server for Travel Booking Tools.

Wraps HTTP mock service (localhost:9130) with abstract tool definitions.
Agent sees tools as function calls, not HTTP APIs.

Tools: get_hotels_prices, get_hotels_address, get_rating_reviews_for_hotels,
       reserve_hotel, get_all_car_rental_companies_in_city,
       get_car_fuel_options, create_calendar_event
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
    "get_hotels_prices": "/travel/hotels/prices",
    "get_hotels_address": "/travel/hotels/address",
    "get_rating_reviews_for_hotels": "/travel/hotels/reviews",
    "reserve_hotel": "/travel/hotels/reserve",
    "get_all_car_rental_companies_in_city": "/travel/cars/companies",
    "get_car_fuel_options": "/travel/cars/fuel_options",
    "create_calendar_event": "/travel/calendar/create",
}


@server.list_tools()
async def list_tools() -> list[Tool]:
    """Return tool definitions matching claw-eval eventplan usertask0."""
    return [
        Tool(
            name="get_hotels_prices",
            description="Get prices for hotels.",
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
            name="get_hotels_address",
            description="Get address for a hotel.",
            inputSchema={
                "type": "object",
                "properties": {
                    "hotel_name": {
                        "type": "string",
                        "description": "Name of the hotel.",
                    },
                },
                "required": ["hotel_name"],
            },
        ),
        Tool(
            name="get_rating_reviews_for_hotels",
            description="Get rating and reviews for hotels.",
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
            name="reserve_hotel",
            description="Reserve a hotel room.",
            inputSchema={
                "type": "object",
                "properties": {
                    "hotel_name": {
                        "type": "string",
                        "description": "Name of the hotel to reserve.",
                    },
                    "check_in": {
                        "type": "string",
                        "description": "Check-in date (YYYY-MM-DD format).",
                    },
                    "check_out": {
                        "type": "string",
                        "description": "Check-out date (YYYY-MM-DD format).",
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
            name="get_all_car_rental_companies_in_city",
            description="Get all car rental companies in a city.",
            inputSchema={
                "type": "object",
                "properties": {
                    "city": {
                        "type": "string",
                        "description": "City name to search for car rental companies.",
                    },
                },
                "required": ["city"],
            },
        ),
        Tool(
            name="get_car_fuel_options",
            description="Get fuel options for a car rental company.",
            inputSchema={
                "type": "object",
                "properties": {
                    "company_name": {
                        "type": "string",
                        "description": "Name of the car rental company.",
                    },
                },
                "required": ["company_name"],
            },
        ),
        Tool(
            name="create_calendar_event",
            description="Create a calendar event.",
            inputSchema={
                "type": "object",
                "properties": {
                    "title": {
                        "type": "string",
                        "description": "Title of the event.",
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
                        "description": "Location of the event.",
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

    endpoint = TOOL_ENDPOINTS[name]
    url = f"{HTTP_BASE_URL}{endpoint}"

    # Map MCP tool arguments to HTTP API arguments
    http_args = _map_arguments(name, arguments)

    try:
        with httpx.Client(timeout=30.0) as client:
            response = client.post(url, json=http_args)
            response.raise_for_status()
            result = response.json()

        return [TextContent(type="text", text=json.dumps(result, indent=2))]
    except httpx.HTTPError as e:
        return [TextContent(type="text", text=f"Error calling {name}: {str(e)}")]


def _map_arguments(name: str, arguments: dict) -> dict:
    """Map MCP tool arguments to HTTP API request body format."""
    if name == "get_rating_reviews_for_hotels":
        # MCP: hotel_names (list) -> HTTP: hotel_name (string, first item)
        hotel_names = arguments.get("hotel_names", [])
        if isinstance(hotel_names, list) and hotel_names:
            return {"hotel_name": hotel_names[0]}
        return {"hotel_name": ""}

    if name == "get_hotels_prices":
        # MCP: hotel_names (list) -> HTTP: hotel_name (string, first item)
        hotel_names = arguments.get("hotel_names", [])
        if isinstance(hotel_names, list) and hotel_names:
            return {"hotel_name": hotel_names[0]}
        return {"hotel_name": ""}

    if name == "reserve_hotel":
        # MCP: hotel_name, check_in, check_out, guests -> HTTP: hotel_name, checkin_date, checkout_date, guest_name
        result = {"hotel_name": arguments.get("hotel_name", "")}
        if arguments.get("check_in"):
            result["checkin_date"] = arguments["check_in"]
        if arguments.get("check_out"):
            result["checkout_date"] = arguments["check_out"]
        return result

    # Most tools pass arguments directly
    return arguments


async def main():
    """Run MCP server via stdio."""
    async with stdio_server() as (read_stream, write_stream):
        await server.run(read_stream, write_stream, server.create_initialization_options())


if __name__ == "__main__":
    import asyncio
    asyncio.run(main())