# Available Tools

## File Operations Tools

| Tool | Description |
|------|-------------|
| read_file | Read a file from the workspace |
| write_file | Write content to a file in the workspace |
| edit_file | Edit an existing file in the workspace |
| download_file | Download a file from a URL to the workspace |
| list_directory | List files in a directory in the workspace |
| execute_command | Execute a shell command (use with caution) |

### read_file

Read a file from the workspace.

**Parameters:**
- path (string, required): Path to the file

**Returns:** File content as text.

### write_file

Write content to a file in the workspace.

**Parameters:**
- path (string, required): Path to write
- content (string, required): Content to write

**Returns:** Confirmation of write operation.

### edit_file

Edit an existing file in the workspace.

**Parameters:**
- path (string, required): Path to the file
- content (string, required): New content

**Returns:** Confirmation of edit operation.

### download_file

Download a file from a URL to the workspace.

**Parameters:**
- url (string, required): URL to download from
- filename (string, required): Filename to save as

**Returns:** Confirmation of download operation.

### list_directory

List files in a directory in the workspace.

**Parameters:**
- path (string, required): Directory path to list

**Returns:** List of directory entries with names, types, and sizes.

### execute_command

Execute a shell command (use with caution).

**Parameters:**
- command (string, required): Command to execute

**Returns:** Command output. Note: commands are logged for audit purposes.