#!/usr/bin/env python3
"""MCP Server for Content Moderation - wraps HTTP mock service with tool schema."""

import asyncio
import json
import httpx
from mcp.server import Server
from mcp.server.stdio import stdio_server
from mcp.types import Tool, TextContent

# HTTP mock service endpoint
MOCK_SERVICE_URL = "http://localhost:9131"

app = Server("content_moderation")


@app.list_tools()
async def list_tools() -> list[Tool]:
    """Define available tools with their schemas."""
    return [
        Tool(
            name="get_account_profiles",
            description="Fetch detailed profile information (names, bios, photos) for the responsible and victim accounts to assess impersonation.",
            inputSchema={
                "type": "object",
                "properties": {
                    "responsible_account_id": {
                        "type": "string",
                        "description": "ID of the responsible (suspected impersonator) account."
                    },
                    "victim_account_id": {
                        "type": "string",
                        "description": "ID of the verified victim account."
                    }
                },
                "required": ["responsible_account_id", "victim_account_id"]
            }
        ),
        Tool(
            name="submit_impersonation_assessment",
            description="Submit final impersonation assessment. Call after step-by-step evaluation to clear (safe) or flag (impersonating) the responsible account.",
            inputSchema={
                "type": "object",
                "properties": {
                    "responsible_account_id": {
                        "type": "string",
                        "description": "ID of the responsible (suspected impersonator) account."
                    },
                    "decision": {
                        "type": "string",
                        "enum": ["clear", "flag"],
                        "description": "'clear' if not impersonating (e.g., fan/parody), 'flag' if impersonating."
                    },
                    "reason": {
                        "type": "string",
                        "description": "Brief reason (e.g., 'fan account', 'impersonation via name/photo match')."
                    }
                },
                "required": ["responsible_account_id", "decision", "reason"]
            }
        )
    ]


@app.call_tool()
async def call_tool(name: str, arguments: dict) -> list[TextContent]:
    """Execute tool by translating to HTTP request to mock service."""
    async with httpx.AsyncClient(timeout=30.0) as client:
        try:
            if name == "get_account_profiles":
                response = await client.post(
                    f"{MOCK_SERVICE_URL}/content-moderation/profiles/get",
                    json=arguments
                )
                response.raise_for_status()
                result = response.json()
                return [TextContent(type="text", text=json.dumps(result, indent=2))]

            elif name == "submit_impersonation_assessment":
                response = await client.post(
                    f"{MOCK_SERVICE_URL}/content-moderation/impersonation/assess",
                    json=arguments
                )
                response.raise_for_status()
                result = response.json()
                return [TextContent(type="text", text=json.dumps(result, indent=2))]

            else:
                return [TextContent(type="text", text=json.dumps({"error": f"Unknown tool: {name}"}))]

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