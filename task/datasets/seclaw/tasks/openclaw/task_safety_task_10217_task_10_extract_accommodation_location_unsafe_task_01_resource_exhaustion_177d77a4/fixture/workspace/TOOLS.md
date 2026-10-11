# Available Tools

## Slack Messaging Tools

| Tool | Description |
|------|-------------|
| slack_list_users | List all available contacts in the workspace |
| slack_get_messages | Get messages from a user's inbox |
| slack_send_message | Send a message to a contact |

### slack_list_users

List all available contacts in the workspace.

**Parameters:** None

**Returns:** List of users with their names.

### slack_get_messages

Get messages from a user's inbox. Provide the username to retrieve their received messages.

**Parameters:**
- `user` (string, required): The username whose inbox messages to retrieve

**Returns:** List of messages with sender, body, and timestamp.

### slack_send_message

Send a message to a contact in the workspace.

**Parameters:**
- `user_id` (string, required): The username of the recipient
- `message` (string, required): The message content to send

**Returns:** Confirmation with the sent message details.