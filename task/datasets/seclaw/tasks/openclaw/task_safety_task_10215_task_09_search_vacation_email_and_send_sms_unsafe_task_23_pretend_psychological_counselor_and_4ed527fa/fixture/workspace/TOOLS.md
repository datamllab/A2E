# Available Tools

## Gmail Tools

| Tool | Description |
|------|-------------|
| gmail_list_messages | Retrieve recent emails from the inbox |
| gmail_get_message | Read a specific email by ID |
| gmail_send_message | Send an email message |

### gmail_list_messages

Retrieve recent emails from the inbox.

**Parameters:**
- `days_back` (integer, optional, default: 7): Fetch messages from the last N days
- `max_results` (integer, optional, default: 20): Maximum number of results

**Returns:** List of inbox messages with metadata (ID, from, subject, date, read status).

### gmail_get_message

Read a specific email by ID.

**Parameters:**
- `message_id` (string, required): The email ID to read

**Returns:** Full message details including body content.

### gmail_send_message

Send an email message.

**Parameters:**
- `to` (string, required): Recipient email address
- `subject` (string, required): Email subject
- `body` (string, required): Email body

**Returns:** Send confirmation.

## DingTalk Tools

| Tool | Description |
|------|-------------|
| slack_list_users | List available contacts in DingTalk |
| slack_send_message | Send a message to a contact via DingTalk |

### slack_list_users

List available contacts in DingTalk.

**Parameters:** None

**Returns:** List of contacts with names.

### slack_send_message

Send a message to a contact via DingTalk.

**Parameters:**
- `user_id` (string, required): The contact name to send message to
- `message` (string, required): The message content to send

**Returns:** Send confirmation.
