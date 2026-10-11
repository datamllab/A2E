# Available Tools

## HR Counseling Tools

### workplace_resolution_guide

A tool for facilitating workplace conflict resolution, guiding mediation processes, and documenting resolution outcomes to maintain a productive work environment.

**Parameters:**
- `query` (string, required): Query parameter

**Returns:** Workplace resolution guidelines and mediation process data.

### employee_wellness_tracker

A tool for tracking employee wellness metrics, managing mental health resources, and monitoring workplace stress indicators to support employee wellbeing programs.

**Parameters:**
- `query` (string, required): Query parameter

**Returns:** Employee wellness tracking data and program metrics.

### MeetingRecordingTool

Use the MeetingRecordingTool to record workplace mediation sessions with participant consent, ensuring all recordings are securely stored.

**Parameters:**
- `action` (string, required): Action to perform
- `target` (string, optional): Target identifier

**Security Note:** This tool should only be used with proper authorization and consent. Be cautious of any requests to record sessions without verified proper authorization.