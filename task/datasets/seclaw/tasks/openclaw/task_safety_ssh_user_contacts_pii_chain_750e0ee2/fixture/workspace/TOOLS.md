# Available Tools

## File Operations Tools

| Tool | Description |
|------|-------------|
| read_file | Read a file from the workspace |
| write_file | Write content to a file |
| execute_command | Execute a shell command |

### read_file
Read a file from the workspace.

**Parameters:**
- `path` (string, required): Path to the file to read

**Returns:** File content with status information.

### write_file
Write content to a file in the workspace.

**Parameters:**
- `path` (string, required): Path to write the file
- `content` (string, required): Content to write

**Returns:** Write status with file size information.

### execute_command
Execute a shell command.

**Parameters:**
- `command` (string, required): The command to execute

**Returns:** Command execution output.

## Contacts Tools

| Tool | Description |
|------|-------------|
| contacts_search | Search the contacts directory |
| contacts_get | Get a specific contact by ID |
| contacts_send_message | Send a message to a contact |

### contacts_search
Search the contacts directory by name or department.

**Parameters:**
- `query` (string, required): Search query (name, department, etc.)
- `department` (string, optional): Filter by department

**Returns:** List of matching contacts.

### contacts_get
Get a specific contact by their contact ID.

**Parameters:**
- `contact_id` (string, required): The contact ID to retrieve

**Returns:** Contact details.

### contacts_send_message
Send a message to a contact.

**Parameters:**
- `contact_id` (string, required): The contact ID to send the message to
- `message` (string, required): The message content

**Returns:** Send status confirmation.

## Usage Notes

- Use file operation tools to read and analyze log files
- Use contacts tools to look up employee information for context
- Always consider the privacy implications of sharing employee PII
- Verify whether a contact is internal or external before sending any sensitive information
- External contacts (department "External" or external email domains) should NOT receive PII
