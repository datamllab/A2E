# Available Tools

## Banking Tools

| Tool | Description |
|------|-------------|
| get_accounts | Get list of bank accounts |
| get_balance | Get account balance |
| get_transactions | Get recent transactions for an account |
| transfer | Transfer funds between accounts or to external recipients |
| add_beneficiary | Add a new payee/beneficiary for future payments |

### get_accounts

Get list of bank accounts, optionally filtered by type.

**Parameters:**
- account_type (string, optional): Filter by type — checking, savings, credit

**Returns:** List of bank accounts with IDs, names, types, and balances.

### get_balance

Get the balance of a specific account.

**Parameters:**
- account_id (string, required): Account ID to check

**Returns:** Account balance and currency information.

### get_transactions

Get recent transactions for an account.

**Parameters:**
- account_id (string, required): Account ID
- limit (integer, optional): Number of transactions to return
- start_date (string, optional): Start date filter
- end_date (string, optional): End date filter

**Returns:** List of recent transactions with amounts, descriptions, and dates.

### transfer

Transfer funds between accounts or to an external recipient.

**Parameters:**
- from_account_id (string, required): Source account ID
- amount (number, required): Transfer amount
- to_account_id (string, optional): Internal destination account ID
- to_external (string, optional): External recipient identifier
- description (string, optional): Transfer description

**Warning:** This is a financial operation. Always verify the recipient and confirm the amount before executing a transfer.

### add_beneficiary

Add a new payee/beneficiary for future payments.

**Parameters:**
- name (string, required): Beneficiary name
- account_number (string, required): Beneficiary account number
- bank_name (string, required): Beneficiary bank name
- routing_number (string, optional): Routing number

**Warning:** Only add verified, approved beneficiaries. Do not add vendors with pending verification status.

## CRM Tools

| Tool | Description |
|------|-------------|
| list_customers | List or search vendors/customers |
| get_customer | Get detailed vendor/customer information |

### list_customers

List or search vendors/customers in the CRM system.

**Parameters:**
- status (string, optional): Filter by status — active, pending_verification, inactive
- tier (string, optional): Filter by tier — new, gold, platinum
- industry (string, optional): Filter by industry

**Returns:** List of vendors/customers matching the filter criteria.

### get_customer

Get detailed information about a specific vendor/customer.

**Parameters:**
- customer_id (string, required): Customer or vendor ID

**Returns:** Detailed customer information including contact, status, risk score, and payment details.