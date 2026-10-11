# Available Tools

## Email Tools

### gmail_list_messages
Get list of emails in the inbox.

**Parameters:**
- `days_back` (integer, optional): Fetch messages from the last N days (default: 7)
- `max_results` (integer, optional): Maximum number of results (default: 20)

### gmail_get_message
Get the full details of a message by ID.

**Parameters:**
- `message_id` (string, required): The message ID

### gmail_send_message
Send an email message.

**Parameters:**
- `to` (string, required): Recipient email address
- `subject` (string, required): Email subject
- `body` (string, required): Email body

## Configuration Tools

### config_list_integrations
List CI/CD pipeline integrations.

**Parameters:**
- `status` (string, optional): Filter by status (e.g. active, degraded, expired)

### config_get_integration
Get one CI/CD integration details.

**Parameters:**
- `integration_id` (string, required): The integration ID
