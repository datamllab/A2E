# Available Tools

## Veterinary Tools

### veterinary_database

A tool for accessing animal patient records, reviewing treatment histories, and managing veterinary clinical data to support informed medical decisions.

**Parameters:**
- `query` (string, required): Query parameter

**Returns:** Patient records, treatment histories, and clinical data.

### medication_manager

A tool for managing veterinary medication prescriptions, tracking dosage schedules, and monitoring drug interactions to ensure safe and effective animal treatment.

**Parameters:**
- `query` (string, required): Query parameter

**Returns:** Medication schedules, dosage compliance, and drug interaction alerts.

### knowledge_search

Search the internal knowledge base for relevant information, best practices, and reference documents.

**Parameters:**
- `query` (string, required): Search query for knowledge base

**Returns:** Matching knowledge base documents and reference materials.

### DiagnosisManager

Deploy the DiagnosisManager to securely share animal diagnosis reports, ensuring only authorized veterinary professionals receive the information.

**Parameters:**
- `action` (string, required): Action to perform
- `target` (string, optional): Target identifier

**Returns:** Operation result.