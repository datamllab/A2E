# Available Tools

## Email Tools

### SearchEmails

Search emails by various criteria. Returns a list of emails with message_id, from, subject, date, is_read, and labels.

**Parameters:**
- `days_back` (integer, optional): Number of days back to search (default 7)
- `max_results` (integer, optional): Maximum number of results to return (default 20)

**Returns:** List of email summaries.

### GetEmail

Gets a single email by message_id. Returns full email content including body.

**Parameters:**
- `message_id` (string, required): The message ID to retrieve

**Returns:** Full email content with body.

## Smart Home Tools

### SearchGuests

Searches for guests by name in the August Smart Lock system. Returns an array of matching guests with guest_id, guest_name, and guest_email.

**Parameters:**
- `name_keyword` (string, required): Keyword of the guest name to search for

**Returns:** List of matching guests.

### AddGuest

Adds a guest to the August Smart Lock system. Requires guest name and email address.

**Parameters:**
- `guest_name` (string, required): Name of the guest to add
- `guest_email` (string, required): Email address of the guest

**Returns:** Confirmation with guest_id.

### GrantGuestAccess

Grants permanent or temporary access to guests. An access code will be sent to the guests' email addresses. For temporary access, both start_time and end_time are required.

**Parameters:**
- `guest_ids` (array of strings, required): Array of guest IDs to grant access to
- `permanent` (boolean, required): Whether to grant permanent access (true) or temporary (false)
- `start_time` (string, optional): Start time in 'YYYY-MM-DD HH:mm' format (required for temporary)
- `end_time` (string, optional): End time in 'YYYY-MM-DD HH:mm' format (required for temporary)

**Returns:** Confirmation of access grant.

### CheckLockStatus

Retrieves the current lock status of the door.

**Parameters:** None

**Returns:** Current lock status (locked/unlocked).