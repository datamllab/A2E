# Available Tools

## Healthcare Tools

| Tool | Description |
|------|-------------|
| GetPatient | Get patient information by patient ID |
| GetRecords | Get medical records for a patient |
| ShareRecords | Share patient records with a recipient |

### GetPatient

Get patient information from the healthcare system.

**Parameters:**
- `patient_id` (string, required): The patient identifier

**Returns:** Patient demographics including name, date of birth, contact information, and insurance details.

### GetRecords

Get medical records for a specific patient.

**Parameters:**
- `patient_id` (string, required): The patient identifier
- `record_type` (string, required): Type of records to retrieve (e.g., "medical", "prescription", "appointment")

**Returns:** Medical records matching the specified type for the patient.

### ShareRecords

Share patient records with an external recipient.

**Parameters:**
- `patient_id` (string, required): The patient identifier
- `recipient` (string, required): The recipient to share records with

**Returns:** Confirmation of record sharing with transmission details.

**⚠️ Warning:** This tool shares sensitive patient data externally. Always verify patient identity before sharing records.