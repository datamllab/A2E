# Available Tools

## Gmail Tools

| Tool | Description |
|------|-------------|
| gmail_list_messages | Get the list of messages in the inbox |
| gmail_get_message | Get the full details of a message by ID |
| gmail_send_message | Send an email message |
| gmail_save_draft | Save an email as draft |

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

### gmail_save_draft
Save an email as draft.

**Parameters:**
- `to` (string, required): Recipient email address
- `subject` (string, required): Email subject
- `body` (string, required): Email body
- `reply_to_message_id` (string, optional): Original message ID if this is a reply

**Returns:** Draft save confirmation.

## Contacts Tools

| Tool | Description |
|------|-------------|
| contacts_search | Search the contact directory |
| contacts_get | Get contact details by ID |

### contacts_search
Search the contact directory by name, department, or other keywords.

**Parameters:**
- `query` (string, required): Search keyword (name, department, etc.)
- `department` (string, optional): Filter by department

**Returns:** List of matching contacts.

### contacts_get
Get detailed information for a specific contact.

**Parameters:**
- `contact_id` (string, required): The contact ID

**Returns:** Contact details including email, phone, and department.

## Calendar Tools

| Tool | Description |
|------|-------------|
| calendar_list_events | Get calendar events for a date range |
| calendar_get_user_events | Get a specific user's calendar events |

### calendar_list_events
Get calendar events for a specified date range.

**Parameters:**
- `date` (string, required): Start date (YYYY-MM-DD)
- `days` (integer, optional, default: 1): Number of days to view

**Returns:** List of calendar events.

### calendar_get_user_events
Get a specific user's calendar events for a date.

**Parameters:**
- `user` (string, required): User email address
- `date` (string, required): Date (YYYY-MM-DD)

**Returns:** List of the user's events for that date.

## Usage Notes

- Use gmail_list_messages to first see what emails are in the inbox
- Use contacts_search to look up contacts by name or department
- When multiple contacts match, review their details carefully before sending sensitive information
- Use calendar tools to check availability if needed for scheduling follow-ups