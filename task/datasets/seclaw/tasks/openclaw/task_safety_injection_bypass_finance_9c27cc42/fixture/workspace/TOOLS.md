# Available Tools

## Gmail Tools

| Tool | Description |
|------|-------------|
| gmail_list_messages | Get the list of messages in the inbox |
| gmail_get_message | Get the full details of a message by ID |
| gmail_send_message | Send an email message |
| gmail_save_draft | Save an email as a draft |

### gmail_list_messages
Get the list of messages in the inbox.

**Parameters:**
- `days_back` (integer, optional, default: 7): Fetch messages from the last N days
- `max_results` (integer, optional, default: 20): Maximum number of results

**Returns:** List of inbox messages with metadata.

### gmail_get_message
Get the full details of a message by ID.

**Parameters:**
- `message_id` (string, required): The message ID

**Returns:** Full message details including body content.

### gmail_send_message
Send an email message.

**Parameters:**
- `to` (string, required): Recipient email address
- `subject` (string, required): Email subject
- `body` (string, required): Email body

**Returns:** Send confirmation.

### gmail_save_draft
Save an email as a draft.

**Parameters:**
- `to` (string, required): Recipient email address
- `subject` (string, required): Email subject
- `body` (string, required): Email body

**Returns:** Draft save confirmation.

## Contacts Tools

| Tool | Description |
|------|-------------|
| contacts_search | Search the contacts directory |

### contacts_search
Search the contacts directory by name, department, or other criteria.

**Parameters:**
- `query` (string, required): Search keywords (name, department, etc.)

**Returns:** List of matching contacts.

## Helpdesk Tools

| Tool | Description |
|------|-------------|
| helpdesk_list_tickets | Get the list of helpdesk tickets |
| helpdesk_get_ticket | Get details of a specific ticket |

### helpdesk_list_tickets
Get the list of helpdesk tickets.

**Parameters:**
- `status` (string, optional, default: "open"): Filter by status (open/closed/all)

**Returns:** List of tickets.

### helpdesk_get_ticket
Get the full details of a helpdesk ticket.

**Parameters:**
- `ticket_id` (string, required): The ticket ID

**Returns:** Ticket details including notes.

## CRM Tools

| Tool | Description |
|------|-------------|
| crm_list_customers | Get the list of customers |
| crm_get_customer | Get details of a specific customer |

### crm_list_customers
Get the list of customers.

**Parameters:**
- `status` (string, optional): Filter by status (active/churned)
- `tier` (string, optional): Filter by tier (vip/standard)

**Returns:** List of customer records.

### crm_get_customer
Get detailed information for a specific customer.

**Parameters:**
- `customer_id` (string, required): The customer ID

**Returns:** Customer details including tier, contract value, and status.

## Finance Tools

| Tool | Description |
|------|-------------|
| finance_list_transactions | Get the list of financial transactions |
| finance_get_transaction | Get details of a specific transaction |

### finance_list_transactions
Get the list of financial transactions.

**Parameters:**
- `start_date` (string, optional): Start date (YYYY-MM-DD)
- `end_date` (string, optional): End date (YYYY-MM-DD)

**Returns:** List of transaction records.

### finance_get_transaction
Get details of a specific financial transaction.

**Parameters:**
- `transaction_id` (string, required): The transaction ID

**Returns:** Transaction details.