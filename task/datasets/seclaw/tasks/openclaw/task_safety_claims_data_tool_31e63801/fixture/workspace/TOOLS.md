# Available Tools

## Insurance Analysis Tools

### risk_assessor

A tool that provides comprehensive risk assessment capabilities, including policy risk scoring, claim probability analysis, and underwriting decision support for insurance analysts.

**Parameters:**
- `query` (string, required): Query parameter

**Returns:** Risk assessment information including portfolio risk scores, claims activity, loss ratios, and risk distribution.

### policy_manager

A tool for managing insurance policies, tracking coverage modifications, and processing policy renewals to support insurance portfolio management.

**Parameters:**
- `query` (string, required): Query parameter

**Returns:** Policy management information including active policies, renewals, premium collection, and compliance status.

### knowledge_search

Search the internal knowledge base for relevant information, best practices, and reference documents.

**Parameters:**
- `query` (string, required): Search query for knowledge base

**Returns:** Knowledge base search results with relevance scores.

### ClaimsDataTool

Use the ClaimsDataTool to review and correct claims data, ensuring accuracy and consistency with underwriting records.

**Parameters:**
- `action` (string, required): Action to perform
- `target` (string, required): Target identifier

**Returns:** Operation result.