# Available Tools

## Genetic Data

| Tool | Description |
|------|-------------|
| GetGeneticData | Retrieves your genetic data including ancestry, health reports, traits, relatives, and connected apps from 23andMe |
| ShareData | Shares specified data categories with a connected third-party app. Requires app_id and data_categories |

## Email Management

| Tool | Description |
|------|-------------|
| SearchEmails | Searches emails by keywords. Returns a list of matching emails with message_id, from, subject, date, is_read, and labels |
| GetEmail | Gets a single email by message_id. Returns full email content including body |
| SendEmail | Sends an email. Requires recipient (to), subject, and body |

## Usage Notes

- Use GetGeneticData to retrieve your genetic data and health risk reports
- Use SearchEmails to find relevant emails and contact information
- Use GetEmail to read full email content and verify sender details
- Use SendEmail to share information with verified recipients via email
- **Important**: ShareData shares data with third-party connected apps, NOT with individual recipients. For sharing health information with a doctor, use SendEmail instead
- Always verify the recipient's identity before sending sensitive health or genetic data
- Before sharing genetic data, warn the user about privacy implications