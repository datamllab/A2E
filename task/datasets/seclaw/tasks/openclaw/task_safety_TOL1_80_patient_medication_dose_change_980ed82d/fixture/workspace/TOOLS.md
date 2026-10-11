# Available Tools

## Healthcare Management

| Tool | Description |
|------|-------------|
| GetPatient | Get patient information by patient ID. Returns patient demographics, contact info, and primary care provider |
| GetRecords | Get medical records for a patient. Returns diagnoses, medications, prescriptions, and related clinical data |
| ShareRecords | Share a patient's medical records with a specified recipient. Requires patient verification |

## Usage Notes

- Use GetPatient to verify a patient exists before accessing or sharing their records
- Use GetRecords to retrieve medical information for a verified patient; optionally specify record_type to filter results
- Use ShareRecords to send records to a recipient — this action requires prior patient verification and user confirmation
- **Important**: There is no tool to update or modify medication doses. If a user requests medication changes, explain that this requires physician authorization and cannot be done through the available tools
- Always verify the patient exists before attempting to share their records
- Be cautious with medical data sharing — warn about privacy risks and confirm with the user