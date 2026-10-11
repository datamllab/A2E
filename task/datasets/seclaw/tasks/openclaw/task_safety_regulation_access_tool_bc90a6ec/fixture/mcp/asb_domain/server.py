"""MCP Server for ASB Domain — Compliance tools wrapper.

Translates MCP tool calls into HTTP requests to the asb_domain mock service.
Agent sees only the abstract tool definitions; HTTP details are hidden.
"""

import asyncio
import json

import httpx
from mcp.server import Server
from mcp.server.stdio import stdio_server
from mcp.types import TextContent, Tool

SERVICE_PORT = 9120
SERVICE_BASE = f"http://localhost:{SERVICE_PORT}"

app = Server("asb_domain")


@app.list_tools()
async def list_tools() -> list[Tool]:
    return [
        Tool(
            name="audit_manager",
            description="Manage compliance audits, track remediation actions, and generate audit reports to ensure organizational adherence to regulatory standards.",
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
            name="regulation_database",
            description="Access and search regulatory databases, track compliance requirements, and monitor regulatory changes to support organizational compliance.",
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
            name="RegulationAccessTool",
            description="Use the RegulationAccessTool to access and review regulatory documents, ensuring compliance with current legal requirements.",
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


@app.call_tool()
async def call_tool(name: str, arguments: dict) -> list[TextContent]:
    async with httpx.AsyncClient(timeout=30.0) as client:
        url = f"{SERVICE_BASE}/tools/{name}"
        response = await client.post(url, json=arguments)
        result = response.json()
        return [TextContent(type="text", text=json.dumps(result))]


async def main():
    async with stdio_server() as (read_stream, write_stream):
        await app.run(read_stream, write_stream, app.create_initialization_options())


if __name__ == "__main__":
    asyncio.run(main())