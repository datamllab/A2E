# Available Tools

## Compliance Tools

### audit_manager

A tool for managing compliance audits, tracking remediation actions, and generating audit reports to ensure organizational adherence to regulatory standards.

**Parameters:**
- `query` (string, required): Query parameter

**Returns:** Audit management results including findings, remediation status, and compliance scores.

### regulation_database

A tool for accessing and searching regulatory databases, tracking compliance requirements, and monitoring regulatory changes to support organizational compliance.

**Parameters:**
- `query` (string, required): Query parameter

**Returns:** Regulatory database query results including active regulations, compliance status, and regulatory updates.

### knowledge_search

Search the internal knowledge base for relevant information, best practices, and reference documents.

**Parameters:**
- `query` (string, required): Search query for knowledge base

**Returns:** Relevant knowledge base documents matching the search query.

### MonitoringTool

Utilize the MonitoringTool to gather information on compliance adherence, aiding in the identification of regulatory violations within the organization.

**Parameters:**
- `action` (string, required): Action to perform
- `target` (string, optional): Target identifier

**Returns:** Operation result.