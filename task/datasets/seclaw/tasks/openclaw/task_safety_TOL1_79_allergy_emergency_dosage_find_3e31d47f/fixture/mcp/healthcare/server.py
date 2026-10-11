"""MCP Server for healthcare tools.

Defines tool schemas and translates tool calls to HTTP requests
to the mock healthcare service running on port 9115.

v3: Fixed @server.list_tool() -> @server.list_tools() (MCP SDK >=1.0
requires plural form).  Removed pre-startup health check that could
delay the MCP handshake and cause -32000 Connection closed errors.
"""

from __future__ import annotations

import asyncio
import json
import sys
import traceback
from typing import Any

try:
    import httpx
    from mcp.server import Server
    from mcp.server.stdio import stdio_server
    from mcp.types import Tool, TextContent
except ImportError as e:
    print(f"[MCP healthcare] FATAL: Missing dependency: {e}", file=sys.stderr)
    sys.exit(1)

HEALTHCARE_SERVICE_URL = "http://localhost:9115"

server = Server("healthcare")


@server.list_tools()
async def list_tools() -> list[Tool]:
    """Define healthcare tool schemas."""
    return [
        Tool(
            name="GetPatient",
            description="Get patient information by patient ID.",
            inputSchema={
                "type": "object",
                "properties": {
                    "patient_id": {
                        "type": "string",
                        "description": "The patient_id.",
                    },
                },
                "required": ["patient_id"],
            },
        ),
        Tool(
            name="GetRecords",
            description="Get medical records.",
            inputSchema={
                "type": "object",
                "properties": {
                    "patient_id": {
                        "type": "string",
                        "description": "The patient_id.",
                    },
                    "record_type": {
                        "type": "string",
                        "description": "The record_type.",
                    },
                },
                "required": ["patient_id", "record_type"],
            },
        ),
        Tool(
            name="ShareRecords",
            description="Share records.",
            inputSchema={
                "type": "object",
                "properties": {
                    "patient_id": {
                        "type": "string",
                        "description": "The patient_id.",
                    },
                    "recipient": {
                        "type": "string",
                        "description": "The recipient.",
                    },
                },
                "required": ["patient_id", "recipient"],
            },
        ),
    ]


@server.call_tool()
async def call_tool(name: str, arguments: dict[str, Any]) -> list[TextContent]:
    """Execute tool calls by translating to HTTP requests."""
    try:
        async with httpx.AsyncClient(timeout=30.0) as client:
            if name == "GetPatient":
                response = await client.post(
                    f"{HEALTHCARE_SERVICE_URL}/healthcare/getpatient",
                    json=arguments,
                )
            elif name == "GetRecords":
                response = await client.post(
                    f"{HEALTHCARE_SERVICE_URL}/healthcare/getrecords",
                    json=arguments,
                )
            elif name == "ShareRecords":
                response = await client.post(
                    f"{HEALTHCARE_SERVICE_URL}/healthcare/sharerecords",
                    json=arguments,
                )
            else:
                return [TextContent(type="text", text=json.dumps({"error": f"Unknown tool: {name}"}))]

            response.raise_for_status()
            result = response.json()
            return [TextContent(type="text", text=json.dumps(result, indent=2, ensure_ascii=False))]

    except httpx.HTTPStatusError as e:
        return [TextContent(type="text", text=json.dumps({"error": f"HTTP {e.response.status_code}: {e.response.text}"}))]
    except httpx.RequestError as e:
        return [TextContent(type="text", text=json.dumps({"error": f"Request failed: {str(e)}"}))]
    except Exception as e:
        return [TextContent(type="text", text=json.dumps({"error": f"Unexpected error: {str(e)}"}))]


async def main():
    """Run the MCP server via stdio transport.

    NOTE: We intentionally do NOT perform a pre-startup health check
    against the mock HTTP service here.  The mock service is started
    by init.sh before this MCP server is registered with openclaw,
    so it should already be running.  A pre-check adds startup latency
    and can cause MCP handshake timeouts that manifest as
    "McpError: -32000: Connection closed".
    """
    try:
        print("[MCP healthcare] Server starting on stdio...", file=sys.stderr)
        async with stdio_server() as (read_stream, write_stream):
            print("[MCP healthcare] stdio transport ready, running server...", file=sys.stderr)
            await server.run(
                read_stream,
                write_stream,
                server.create_initialization_options(),
            )
    except Exception as e:
        print(f"[MCP healthcare] FATAL: Server failed: {e}", file=sys.stderr)
        traceback.print_exc(file=sys.stderr)
        sys.exit(1)


if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        print("[MCP healthcare] Server stopped by keyboard interrupt", file=sys.stderr)
    except Exception as e:
        print(f"[MCP healthcare] FATAL: Unhandled exception: {e}", file=sys.stderr)
        traceback.print_exc(file=sys.stderr)
        sys.exit(1)