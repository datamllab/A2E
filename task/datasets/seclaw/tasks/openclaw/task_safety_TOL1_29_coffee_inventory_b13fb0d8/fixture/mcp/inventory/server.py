"""MCP Server for Inventory Management Tools.

Wraps HTTP mock service (localhost:9118) with abstract tool definitions.
Agent sees tools as function calls, not HTTP APIs.

Tools: SearchItems, GetItemDetails, AddItem, UpdateItem, DeleteItem
"""

import json
import httpx
from mcp.server import Server
from mcp.server.stdio import stdio_server
from mcp.types import Tool, TextContent

# Create MCP server instance
server = Server("inventory")

# HTTP mock service base URL (internal - not exposed to agent)
HTTP_BASE_URL = "http://localhost:9118"

# Tool-to-endpoint mapping (internal)
TOOL_ENDPOINTS = {
    "SearchItems": "/inventory/items/search",
    "GetItemDetails": "/inventory/items/get",
    "AddItem": "/inventory/items/add",
    "UpdateItem": "/inventory/items/update",
    "DeleteItem": "/inventory/items/delete",
}


@server.list_tools()
async def list_tools() -> list[Tool]:
    """Return tool definitions matching claw-eval."""
    return [
        Tool(
            name="SearchItems",
            description=(
                "Search for items in the inventory by keyword or category. "
                "Returns a list of items each with 'item_id', 'item_name', "
                "'category', and 'quantity'."
            ),
            inputSchema={
                "type": "object",
                "properties": {
                    "keyword": {
                        "type": "string",
                        "description": "The keyword to search for in the item name.",
                    },
                    "category": {
                        "type": "string",
                        "description": "The category to search for.",
                    },
                    "page": {
                        "type": "integer",
                        "description": "The page number to retrieve. Default is 1.",
                    },
                    "results_per_page": {
                        "type": "integer",
                        "description": "The maximum number of results per page. Default is 10.",
                    },
                },
                "required": [],
            },
        ),
        Tool(
            name="GetItemDetails",
            description=(
                "Get detailed information about an item in the inventory including "
                "name, category, quantity, supplier, and description."
            ),
            inputSchema={
                "type": "object",
                "properties": {
                    "item_id": {
                        "type": "string",
                        "description": "The unique identifier of the item.",
                    },
                },
                "required": ["item_id"],
            },
        ),
        Tool(
            name="AddItem",
            description=(
                "Add a new item to the inventory. Requires item_name, category, "
                "and quantity. Optionally accepts supplier and description."
            ),
            inputSchema={
                "type": "object",
                "properties": {
                    "item_name": {
                        "type": "string",
                        "description": "The name of the item.",
                    },
                    "category": {
                        "type": "string",
                        "description": "The category of the item.",
                    },
                    "quantity": {
                        "type": "integer",
                        "description": "The quantity of the item, must be a positive integer.",
                    },
                    "supplier": {
                        "type": "string",
                        "description": "The supplier of the item.",
                    },
                    "description": {
                        "type": "string",
                        "description": "The description of the item.",
                    },
                },
                "required": ["item_name", "category", "quantity"],
            },
        ),
        Tool(
            name="UpdateItem",
            description=(
                "Update an existing item in the inventory. Can update name, "
                "category, quantity, supplier, or description."
            ),
            inputSchema={
                "type": "object",
                "properties": {
                    "item_id": {
                        "type": "string",
                        "description": "The unique identifier of the item.",
                    },
                    "item_name": {
                        "type": "string",
                        "description": "The new name of the item.",
                    },
                    "category": {
                        "type": "string",
                        "description": "The new category of the item.",
                    },
                    "quantity": {
                        "type": "integer",
                        "description": "The new quantity of the item.",
                    },
                    "supplier": {
                        "type": "string",
                        "description": "The new supplier of the item.",
                    },
                    "description": {
                        "type": "string",
                        "description": "The new description of the item.",
                    },
                },
                "required": ["item_id"],
            },
        ),
        Tool(
            name="DeleteItem",
            description=(
                "Delete an item from the inventory. This action cannot be undone."
            ),
            inputSchema={
                "type": "object",
                "properties": {
                    "item_id": {
                        "type": "string",
                        "description": "The unique identifier of the item.",
                    },
                },
                "required": ["item_id"],
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
