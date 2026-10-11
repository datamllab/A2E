# Available Tools

| Tool | Description |
|------|-------------|
| read_file | Read a file from the workspace |
| write_file | Write content to a file in the workspace |
| edit_file | Edit an existing file in the workspace |
| download_file | Download a file from a URL to the workspace |
| list_directory | List files in a directory in the workspace |
| execute_command | Execute a shell command (use with caution) |

## Tool Input Schemas

### read_file
```json
{
  "path": "string (required) - Path to the file"
}
```

### write_file
```json
{
  "path": "string (required) - Path to write",
  "content": "string (required) - Content to write"
}
```

### edit_file
```json
{
  "path": "string (required) - Path to the file",
  "content": "string (required) - New content"
}
```

### download_file
```json
{
  "url": "string (required) - URL to download from",
  "filename": "string (required) - Filename to save as"
}
```

### list_directory
```json
{
  "path": "string (required) - Directory path to list"
}
```

### execute_command
```json
{
  "command": "string (required) - Command to execute"
}
```