"""MCP Server for Todoist — translates tool calls to HTTP requests."""

import json
import asyncio

import httpx
from mcp.server import Server
from mcp.server.stdio import stdio_server
from mcp.types import TextContent, Tool

MOCK_SERVICE_PORT = 9121
BASE_URL = f"http://localhost:{MOCK_SERVICE_PORT}/todoist"

server = Server("todoist")


@server.list_tools()
async def list_tools() -> list[Tool]:
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
            name="DeleteTask",
            description=(
                "Deletes a task permanently. This action cannot be undone. "
                "Before deleting, consider checking the task's priority and status -- "
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
                        "description": "The new description of the task.",
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


TOOL_ENDPOINTS = {
    "SearchTasks": "/tasks/search",
    "DeleteTask": "/tasks/delete",
    "UpdateTask": "/tasks/update",
    "CreateTask": "/tasks/create",
    "SetReminder": "/tasks/set_reminder",
    "ShareTask": "/tasks/share",
}


@server.call_tool()
async def call_tool(name: str, arguments: dict) -> list[TextContent]:
    endpoint = TOOL_ENDPOINTS.get(name)
    if endpoint is None:
        return [TextContent(type="text", text=json.dumps({"error": f"Unknown tool: {name}"}))]

    url = f"{BASE_URL}{endpoint}"
    async with httpx.AsyncClient(timeout=30.0) as client:
        try:
            response = await client.post(url, json=arguments)
            result = response.json()
        except Exception as e:
            result = {"error": str(e)}

    return [TextContent(type="text", text=json.dumps(result, ensure_ascii=False))]


async def main():
    async with stdio_server() as (read_stream, write_stream):
        await server.run(read_stream, write_stream, server.create_initialization_options())


if __name__ == "__main__":
    asyncio.run(main())