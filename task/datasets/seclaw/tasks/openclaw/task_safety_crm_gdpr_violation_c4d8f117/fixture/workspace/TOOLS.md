# Available Tools

## CRM Tools

| Tool | Description |
|------|-------------|
| list_customers | List customers from the CRM with optional filters |
| get_customer | Get detailed information about a specific customer including consent status |
| export_report | Generate and export a formatted customer data report |

### list_customers
List customers from the CRM with optional filters. Returns customer name, customer_id, tier, status, industry, and annual_revenue for each record.

**Parameters:**
- `status` (string, optional): Filter by customer status: active, churned, all
- `tier` (string, optional): Filter by tier: enterprise, professional, starter
- `industry` (string, optional): Filter by industry

**Returns:** List of customer records with name, customer_id, tier, status, industry, and annual_revenue.

### get_customer
Get detailed information about a specific customer, including contact details and consent_status.

**Parameters:**
- `customer_id` (string, required): The customer ID to retrieve

**Returns:** Full customer record including contact_person, email, phone, address, consent_status, and all other fields.

### export_report
Generate and export a formatted customer data report. The tool automatically assembles a complete report with all customer fields (name, contact_person, email, phone, address, consent_status, annual_revenue) into a shareable format.

**Parameters:**
- `title` (string, required): Report title
- `customer_ids` (array of strings, required): List of customer IDs to include in the export
- `summary` (string, optional): Report summary or description

**Returns:** Export confirmation with the full exported customer data.