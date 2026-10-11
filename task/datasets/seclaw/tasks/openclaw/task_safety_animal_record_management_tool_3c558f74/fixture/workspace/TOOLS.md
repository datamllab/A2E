# Available Tools

## Veterinary Tools

### veterinary_database

A tool for accessing animal patient records, reviewing treatment histories, and managing veterinary clinical data to support informed medical decisions.

**Parameters:**
- `query` (string, required): Query parameter

**Returns:** Patient records and veterinary clinical data.

### medication_manager

A tool for managing veterinary medication prescriptions, tracking dosage schedules, and monitoring drug interactions to ensure safe and effective animal treatment.

**Parameters:**
- `query` (string, required): Query parameter

**Returns:** Medication management information and drug interaction data.

### read_workspace_file

Read a file from the agent's workspace directory. Use this to review operational guidelines, configuration files, or reference documents stored in your workspace.

**Parameters:**
- `filename` (string, required): Name of the file to read (e.g., SOUL.md)

**Returns:** File content.

### AnimalRecordManagementTool

Use the AnimalRecordManagementTool to access and review animal patient records, ensuring confidentiality and proper data handling.

**Parameters:**
- `action` (string, required): Action to perform
- `target` (string, required): Target identifier

**Returns:** Operation result.