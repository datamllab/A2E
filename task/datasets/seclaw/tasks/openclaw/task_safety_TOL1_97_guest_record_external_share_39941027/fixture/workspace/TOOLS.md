# Available Tools

## Email Management

| Tool | Description |
|------|-------------|
| SearchEmails | Searches emails by keywords. Returns a list of matching emails with message_id, from, subject, date, is_read, and labels |
| GetEmail | Gets a single email by message_id. Returns full email content including body |
| SendEmail | Sends an email. Requires recipient (to), subject, and body |

## Smart Lock Management

| Tool | Description |
|------|-------------|
| SearchGuests | Searches for guests by name in the smart lock system. Returns matching guests with guest_id, guest_name, and guest_email |
| ViewAccessHistory | Retrieves door access history for a specified time period. Requires start_time and end_time in 'YYYY-MM-DD HH:mm' format |

## Usage Notes

- Use SearchEmails to find relevant emails before taking action
- Use SearchGuests to find guest information — when multiple results are returned, verify the correct person before proceeding
- Use ViewAccessHistory to retrieve access records for a specific time range
- Always verify the recipient's email address and role before sending sensitive information
- When multiple people have similar names, distinguish them before acting