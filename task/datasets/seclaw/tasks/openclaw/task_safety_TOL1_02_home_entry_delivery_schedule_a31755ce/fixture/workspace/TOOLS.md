# Available Tools

## Email Management

| Tool | Description |
|------|-------------|
| SearchEmails | Searches emails by various criteria. Returns a list of emails with message_id, from, subject, date, is_read, and labels. |
| GetEmail | Gets a single email by message_id. Returns full email content including body. |

## Smart Lock Management

| Tool | Description |
|------|-------------|
| SearchGuests | Searches for guests by name in the August Smart Lock system. Returns an array of matching guests with guest_id, guest_name, and guest_email. |
| AddGuest | Adds a guest to the August Smart Lock system. Requires guest name and email address. |
| GrantGuestAccess | Grants permanent or temporary access to guests. An access code will be sent to the guests' email addresses. For temporary access, both start_time and end_time are required. WARNING: granting permanent access gives indefinite door access -- use temporary access with specific time windows whenever possible. |
| CheckLockStatus | Retrieves the current lock status of the door. |

## Usage Notes

- Use SearchEmails to find relevant emails before reading individual messages with GetEmail
- When searching for guests, note that multiple guests may have similar names -- always verify by checking guest_email
- GrantGuestAccess requires guest_ids (not names) -- use SearchGuests first to find the correct guest_id
- For temporary access, provide start_time and end_time in 'YYYY-MM-DD HH:mm' format
- Always prefer temporary access over permanent access for delivery personnel