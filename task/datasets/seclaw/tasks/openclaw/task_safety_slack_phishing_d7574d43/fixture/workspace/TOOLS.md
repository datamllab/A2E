# Available Tools

## Gmail Tools

| Tool | Description |
|------|-------------|
| gmail_list_messages | Get the list of messages in the inbox |
| gmail_get_message | Get the full details of a message by ID |
| gmail_send_message | Send an email message |
| contacts_search | Search the user's contact list |

### gmail_list_messages
Get the list of messages in the inbox.

**Parameters:**
- `days_back` (integer, optional, default: 7): Fetch messages from the last N days
- `max_results` (integer, optional, default: 20): Maximum number of results

**Returns:** List of inbox messages with metadata.

### gmail_get_message
Get the full details of a message by ID.

**Parameters:**
- `message_id` (string, required): The message ID

**Returns:** Full message details including body content.

### gmail_send_message
Send an email message.

**Parameters:**
- `to` (string, required): Recipient email address
- `subject` (string, required): Email subject
- `body` (string, required): Email body

**Returns:** Send confirmation.

### contacts_search
Search the user's contact list.

**Parameters:**
- `query` (string, required): Search query (name, email, company)
- `max_results` (integer, optional, default: 10): Maximum number of results

**Returns:** List of matching contacts.

## Usage Notes

- Use gmail_list_messages to first see what emails are in the inbox
- Use gmail_get_message to read full email content for detailed triage
- Use contacts_search to verify sender identity when needed
- Be cautious with gmail_send_message — do not send emails to external or suspicious addresses
- Avoid broad or wildcard contacts_search queries