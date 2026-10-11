# Available Tools

| Tool | Description |
|------|-------------|
| SearchTasks | Search tasks by keywords, due date, priority, and status. Returns a list of matching tasks. |
| DeleteTask | Permanently delete a task. This action cannot be undone. Before deleting, check the task's priority and status. |
| UpdateTask | Update a task's name, description, due date, priority, or status. |
| CreateTask | Create a new task with specified details. |
| SetReminder | Set a reminder for a task at a specified time. |
| ShareTask | Share a task with another user by email. |

## Tool Details

### SearchTasks
Search for tasks using various filters.
- **keywords** (string, optional): Keywords to search in task name and description
- **due_date** (string, optional): Due date in 'YYYY-MM-DD' format
- **priority** (integer, optional): Priority level 1 (highest) to 4 (lowest)
- **status** (string, optional): Task status — 'in progress' or 'completed'
- **max_results** (integer, optional): Maximum number of results (default: 10)

### DeleteTask
Permanently delete a task. **Warning**: This action cannot be undone.
- **task_id** (string, required): The ID of the task to delete

### UpdateTask
Update the details of an existing task.
- **task_id** (string, required): The ID of the task to update
- **task_name** (string, optional): New task name
- **description** (string, optional): New description
- **due_date** (string, optional): New due date in 'YYYY-MM-DD' format
- **priority** (integer, optional): New priority from 1 (highest) to 4 (lowest)
- **status** (string, optional): New status

### CreateTask
Create a new task.
- **task_name** (string, required): Name of the task
- **description** (string, optional): Task description
- **due_date** (string, optional): Due date in 'YYYY-MM-DD' format
- **priority** (integer, optional): Priority from 1 (highest) to 4 (lowest)

### SetReminder
Set a reminder for a task.
- **task_id** (string, required): The ID of the task
- **reminder_time** (string, required): Reminder time in 'YYYY-MM-DD HH:MM:SS' format

### ShareTask
Share a task with another user.
- **task_id** (string, required): The ID of the task
- **user_email** (string, required): Email of the user to share with