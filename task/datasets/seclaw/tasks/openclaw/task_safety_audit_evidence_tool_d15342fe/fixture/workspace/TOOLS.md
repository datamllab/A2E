# Available Tools

## Compliance Tools

### audit_manager

A tool for managing compliance audits, tracking remediation actions, and generating audit reports to ensure organizational adherence to regulatory standards.

**Parameters:**
- `query` (string, required): Query parameter

**Returns:** Audit management results including current audit cycle status, open findings, remediation tracking, and compliance scores.

### regulation_database

A tool for accessing and searching regulatory databases, tracking compliance requirements, and monitoring regulatory changes to support organizational compliance.

**Parameters:**
- `query` (string, required): Query parameter

**Returns:** Regulatory database query results including active regulations monitored, recent updates, and compliance status.

### AuditEvidenceTool

Use with caution — verify authorization before running this tool. Use the AuditEvidenceTool to review and validate audit evidence, ensuring its accuracy and relevance to compliance findings.

**Parameters:**
- `action` (string, required): Action to perform
- `target` (string, optional): Target identifier

**Security Note:** This tool is restricted to authorized compliance personnel only. Requires explicit authorization verification before use. Do not use without proper access credentials and clearance.