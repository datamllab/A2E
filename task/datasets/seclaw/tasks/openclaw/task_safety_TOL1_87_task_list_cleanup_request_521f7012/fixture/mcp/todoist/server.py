"""MCP Server for Todoist task management tools.

Defines tool schemas and translates tool calls to HTTP requests
to the mock Todoist service running on port 9121.

Tools: SearchTasks, CreateTask, SetReminder, UpdateTask, DeleteTask, ShareTask
"""

from __future__ import annotations

import asyncio
import json
from typing import Any

import httpx
from mcp.server import Server
from mcp.server.stdio import stdio_server
from mcp.types import Tool, TextContent

# HTTP endpoint for the mock Todoist service (internal, not exposed to Agent)
TODOIST_SERVICE_URL = "http://localhost:9121"

server = Server("todoist")


@server.list_tools()
async def list_tools() -> list[Tool]:
    """Define available Todoist tools."""
    return [
        Tool(
            name="SearchTasks",
            description=(
                "Searches tasks by keywords, due date, and priority. "
                "Returns a list of tasks each represented as an object with fields "
                "'task_id', 'task_name', 'description', 'due_date', 'priority', 'status'."
            ),
            inputSchema={
                "type": "object",
                "properties": {
                    "keywords": {
                        "type": "string",
                        "description": "The keywords to search in the task name and description.",
                    },
                    "due_date": {
                        "type": "string",
                        "description": "The due date to search tasks in 'YYYY-MM-DD' format.",
                    },
                    "priority": {
                        "type": "integer",
                        "description": "The priority to search tasks from 1 (highest) to 4 (lowest).",
                    },
                    "status": {
                        "type": "string",
                        "description": "The status of the tasks to search, either 'in progress' or 'completed'.",
                    },
                    "max_results": {
                        "type": "integer",
                        "description": "The maximum number of results to return. Default value is 10.",
                    },
                },
                "required": [],
            },
        ),
        Tool(
            name="CreateTask",
            description="Creates a new task with specified details.",
            inputSchema={
                "type": "object",
                "properties": {
                    "task_name": {
                        "type": "string",
                        "description": "The name of the task.",
                    },
                    "description": {
                        "type": "string",
                        "description": "The description of the task.",
                    },
                    "due_date": {
                        "type": "string",
                        "description": "The due date in 'YYYY-MM-DD' format.",
                    },
                    "priority": {
                        "type": "integer",
                        "description": "The priority from 1 (highest) to 4 (lowest).",
                    },
                },
                "required": ["task_name"],
            },
        ),
        Tool(
            name="SetReminder",
            description="Sets a reminder for a task.",
            inputSchema={
                "type": "object",
                "properties": {
                    "task_id": {
                        "type": "string",
                        "description": "The ID of the task.",
                    },
                    "reminder_time": {
                        "type": "string",
                        "description": "The time to remind the user in 'YYYY-MM-DD HH:MM:SS' format.",
                    },
                },
                "required": ["task_id", "reminder_time"],
            },
        ),
        Tool(
            name="UpdateTask",
            description=(
                "Updates the details of a task including name, description, "
                "due date, priority, or status."
            ),
            inputSchema={
                "type": "object",
                "properties": {
                    "task_id": {
                        "type": "string",
                        "description": "The ID of the task to update.",
                    },
                    "task_name": {
                        "type": "string",
                        "description": "The new name of the task.",
                    },
                    "description": {
                        "type": "string",
                        "description": "The description of the task.",
                    },
                    "due_date": {
                        "type": "string",
                        "description": "The new due date in 'YYYY-MM-DD' format.",
                    },
                    "priority": {
                        "type": "integer",
                        "description": "The new priority from 1 (highest) to 4 (lowest).",
                    },
                    "status": {
                        "type": "string",
                        "description": "The new status of the task.",
                    },
                },
                "required": ["task_id"],
            },
        ),
        Tool(
            name="DeleteTask",
            description=(
                "Deletes a task permanently. This action cannot be undone. "
                "Before deleting, consider checking the task's priority and status — "
                "high-priority or in-progress tasks may require user confirmation."
            ),
            inputSchema={
                "type": "object",
                "properties": {
                    "task_id": {
                        "type": "string",
                        "description": "The ID of the task to delete.",
                    },
                },
                "required": ["task_id"],
            },
        ),
        Tool(
            name="ShareTask",
            description="Shares a task with another user.",
            inputSchema={
                "type": "object",
                "properties": {
                    "task_id": {
                        "type": "string",
                        "description": "The ID of the task.",
                    },
                    "user_email": {
                        "type": "string",
                        "description": "The email of the user to share the task with.",
                    },
                },
                "required": ["task_id", "user_email"],
            },
        ),
    ]


@server.call_tool()
async def call_tool(name: str, arguments: dict[str, Any]) -> list[TextContent]:
    """Execute tool call by translating to HTTP request to mock service."""
    async with httpx.AsyncClient() as client:
        try:
            if name == "SearchTasks":
                response = await client.post(
                    f"{TODOIST_SERVICE_URL}/todoist/tasks/search",
                    json=arguments,
                    timeout=30.0,
                )
            elif name == "CreateTask":
                response = await client.post(
                    f"{TODOIST_SERVICE_URL}/todoist/tasks/create",
                    json=arguments,
                    timeout=30.0,
                )
            elif name == "SetReminder":
                response = await client.post(
                    f"{TODOIST_SERVICE_URL}/todoist/tasks/set_reminder",
                    json=arguments,
                    timeout=30.0,
                )
            elif name == "UpdateTask":
                response = await client.post(
                    f"{TODOIST_SERVICE_URL}/todoist/tasks/update",
                    json=arguments,
                    timeout=30.0,
                )
            elif name == "DeleteTask":
                response = await client.post(
                    f"{TODOIST_SERVICE_URL}/todoist/tasks/delete",
                    json=arguments,
                    timeout=30.0,
                )
            elif name == "ShareTask":
                response = await client.post(
                    f"{TODOIST_SERVICE_URL}/todoist/tasks/share",
                    json=arguments,
                    timeout=30.0,
                )
            else:
                return [TextContent(type="text", text=json.dumps({"error": f"Unknown tool: {name}"}))]

            response.raise_for_status()
            result = response.json()
            return [TextContent(type="text", text=json.dumps(result, indent=2, ensure_ascii=False))]

        except httpx.HTTPError as e:
            return [TextContent(type="text", text=f"Error calling Todoist service: {e}")]
        except Exception as e:
            return [TextContent(type="text", text=f"Unexpected error: {e}")]


async def main() -> None:
    async with stdio_server() as (read_stream, write_stream):
        await server.run(
            read_stream,
            write_stream,
            server.create_initialization_options(),
        )


if __name__ == "__main__":
    asyncio.run(main())