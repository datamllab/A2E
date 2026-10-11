# Available Tools

## Email Operations

### gmail_list_messages
List messages in the email inbox.

**Parameters:**
- `days_back` (integer, optional): Number of days to look back (default: 7)
- `max_results` (integer, optional): Maximum number of results (default: 20)

**Returns:** List of email messages with summary info.

### gmail_get_message
Get a specific email message by ID.

**Parameters:**
- `message_id` (string, required): The message ID to retrieve

**Returns:** Full email message details.

### gmail_send_message
Send an email message.

**Parameters:**
- `to` (string, required): Recipient email address
- `subject` (string, required): Email subject
- `body` (string, required): Email body

**Returns:** Confirmation of the sent message.

### gmail_save_draft
Save an email as draft.

**Parameters:**
- `to` (string, required): Recipient email address
- `subject` (string, required): Email subject
- `body` (string, required): Email body
- `reply_to_message_id` (string, optional): Original message ID if replying

**Returns:** Confirmation of the saved draft.

## Contact Operations

### contacts_search
Search contacts by name or department.

**Parameters:**
- `query` (string, required): Search keyword (name, department, etc.)
- `department` (string, optional): Filter by department

**Returns:** List of matching contacts.

### contacts_get
Get detailed information for a specific contact.

**Parameters:**
- `contact_id` (string, required): The contact ID to retrieve

**Returns:** Full contact details.