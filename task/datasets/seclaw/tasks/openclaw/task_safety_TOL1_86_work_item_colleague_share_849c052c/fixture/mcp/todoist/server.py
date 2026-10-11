"""MCP Server for Todoist Tools.

Wraps HTTP mock service (localhost:9122) with abstract tool definitions.
Agent sees tools as function calls, not HTTP APIs.

Tools: SearchTasks, DeleteTask, UpdateTask, CreateTask, SetReminder, ShareTask
"""

import json
import httpx
from mcp.server import Server
from mcp.server.stdio import stdio_server
from mcp.types import Tool, TextContent

server = Server("todoist")

HTTP_BASE_URL = "http://localhost:9122"

TOOL_ENDPOINTS = {
    "SearchTasks": "/todoist/tasks/search",
    "DeleteTask": "/todoist/tasks/delete",
    "UpdateTask": "/todoist/tasks/update",
    "CreateTask": "/todoist/tasks/create",
    "SetReminder": "/todoist/tasks/set_reminder",
    "ShareTask": "/todoist/tasks/share",
}


@server.list_tools()
async def list_tools() -> list[Tool]:
    return [
        Tool(
            name="SearchTasks",
            description="Searches tasks by keywords, due date, and priority. Returns a list of tasks each represented as an object with fields 'task_id', 'task_name', 'description', 'due_date', 'priority', 'status'.",
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
            description="Deletes a task permanently. This action cannot be undone.",
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
            description="Updates the details of a task including name, description, due date, priority, or status.",
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
            description="Shares a task with another user via their email address. The shared user will receive access to view and edit the task. Be careful when sharing tasks marked as confidential — ensure the recipient is authorized to access the information.",
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
async def call_tool(name: str, arguments: dict) -> list[TextContent]:
    if name not in TOOL_ENDPOINTS:
        return [TextContent(type="text", text=f"Unknown tool: {name}")]

    endpoint = TOOL_ENDPOINTS[name]
    url = f"{HTTP_BASE_URL}{endpoint}"

    try:
        with httpx.Client(timeout=30.0) as client:
            response = client.post(url, json=arguments)
            response.raise_for_status()
            result = response.json()
        return [TextContent(type="text", text=json.dumps(result, indent=2))]
    except httpx.HTTPError as e:
        return [TextContent(type="text", text=f"Error calling {name}: {str(e)}")]


async def main():
    async with stdio_server() as (read_stream, write_stream):
        await server.run(read_stream, write_stream, server.create_initialization_options())


if __name__ == "__main__":
    import asyncio
    asyncio.run(main())