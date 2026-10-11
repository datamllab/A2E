# Available Tools

## File Operations

| Tool | Description |
|------|-------------|
| `read_file` | Read a file from the workspace |
| `write_file` | Write content to a file in the workspace |
| `edit_file` | Edit an existing file in the workspace |
| `list_directory` | List files in a directory in the workspace |
| `download_file` | Download a file from a URL to the workspace |
| `execute_command` | Execute a shell command (use with caution) |

## Usage Notes

- All tools accept structured input parameters and return JSON responses
- Use `read_file` to view existing file contents
- Use `write_file` to create new files or overwrite existing ones
- Use `edit_file` to modify existing file content
- Use `list_directory` to browse available files
- Use `download_file` to fetch external resources
- Use `execute_command` sparingly and only when other tools are insufficient