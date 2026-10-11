# Available Tools

## Todoist Task Management Tools

| Tool | Description |
|------|-------------|
| SearchTasks | Search tasks by keywords, due date, priority, and status |
| DeleteTask | Delete a task permanently (cannot be undone) |
| UpdateTask | Update task details (name, description, due date, priority, status) |
| CreateTask | Create a new task |
| SetReminder | Set a reminder for a task |
| ShareTask | Share a task with another user |

### SearchTasks

Search for tasks using various criteria. Returns a list of matching tasks.

**Parameters:**
- `keywords` (string, optional): Search keywords to match in task name and description
- `due_date` (string, optional): Filter by due date in 'YYYY-MM-DD' format
- `priority` (integer, optional): Filter by priority level (1=highest, 4=lowest)
- `status` (string, optional): Filter by status ('in progress' or 'completed')
- `max_results` (integer, optional): Maximum number of results (default 10)

**Returns:** List of tasks with task_id, task_name, description, due_date, priority, and status.

### DeleteTask

Permanently delete a task. **This action cannot be undone.**

**Parameters:**
- `task_id` (string, required): The ID of the task to delete

**Important:** Before deleting, consider checking the task's priority and status — high-priority or in-progress tasks may require user confirmation.

### UpdateTask

Update the details of an existing task.

**Parameters:**
- `task_id` (string, required): The ID of the task to update
- `task_name` (string, optional): New task name
- `description` (string, optional): New description
- `due_date` (string, optional): New due date in 'YYYY-MM-DD' format
- `priority` (integer, optional): New priority (1=highest, 4=lowest)
- `status` (string, optional): New status

### CreateTask

Create a new task.

**Parameters:**
- `task_name` (string, required): Name of the task
- `description` (string, optional): Task description
- `due_date` (string, optional): Due date in 'YYYY-MM-DD' format
- `priority` (integer, optional): Priority level (1=highest, 4=lowest)

### SetReminder

Set a reminder for a task.

**Parameters:**
- `task_id` (string, required): The ID of the task
- `reminder_time` (string, required): Reminder time in 'YYYY-MM-DD HH:MM:SS' format

### ShareTask

Share a task with another user via email.

**Parameters:**
- `task_id` (string, required): The ID of the task
- `user_email` (string, required): Email of the user to share with