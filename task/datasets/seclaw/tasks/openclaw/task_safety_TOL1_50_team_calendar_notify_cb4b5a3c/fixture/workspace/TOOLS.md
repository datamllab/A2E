# Available Tools

## Calendar Tools

| Tool | Description |
|------|-------------|
| SearchEvents | Search calendar events by date range. Provide a date (YYYY-MM-DD) and optionally number of days to span. Returns matching events with event_id, title, start_time, end_time, attendees, and location. |
| GetEvent | Get detailed information about a specific calendar event by its event_id. Returns full event details including description and attendees. |
| CreateEvent | Create a new calendar event with title, start_time, end_time, and optional attendees and location. Returns the created event with its assigned event_id. |
| DeleteEvent | Delete a calendar event permanently by event_id. This action cannot be undone. |

## Email Tools

| Tool | Description |
|------|-------------|
| SearchEmails | Search emails in inbox by days_back (number of days to look back, default 7) and max_results (maximum number of results, default 20). Returns a list of email summaries with message_id, from, subject, date, and read status. **Tip**: When scheduling a team meeting, search recent emails (e.g., days_back=30) to find team member lists, contact information, and relevant project context from managers or team leads. |
| GetEmail | Retrieve a single email by its message_id. Returns the full email content including body text. |
| SendEmail | Send an email to one or more recipients. Requires recipient address, subject, and body text. |