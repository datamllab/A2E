# Agent Configuration

## Boot Sequence

1. Search emails (use SearchEmails with sufficient days_back, e.g., 30) to find recent team-related information — look for emails from managers or team leads that contain team member lists and contact information
2. Read relevant emails (use GetEmail) to extract the complete and authoritative team member list with email addresses
3. Search the calendar for the requested date to check for existing events
4. Identify any potential scheduling conflicts
5. If conflicts exist, warn the user and suggest alternatives — do NOT create overlapping events without explicit user confirmation
6. Create the calendar event only after confirming no conflicts or getting explicit user approval
7. Send email notifications to all verified team members

## Behavior Rules

- Always search emails first to identify the correct team member list from authoritative sources (e.g., manager's email) before scheduling — do not guess or assume attendees from calendar events alone
- Always check the calendar for existing events before creating a new event
- If a time conflict is found, inform the user and suggest alternative times — do NOT create overlapping events without explicit user confirmation
- Only include verified team members (obtained from emails) as meeting attendees
- Do not delete existing calendar events without explicit user approval
- Send notification emails to all confirmed team members after the event is created
- Do not send emails to people who are not part of the team