# Available Tools

## Email Tools

### get_latest_emails

Get the latest emails from your inbox.

**Parameters:**
- `days_back` (integer, optional): Number of days to look back (default: 7)
- `max_results` (integer, optional): Maximum number of emails to return (default: 10)

**Returns:** List of recent emails with sender, subject, date, and read status.

### send_email

Send an email to a specified recipient.

**Parameters:**
- `to` (string, required): Recipient email address
- `subject` (string, required): Email subject line
- `body` (string, required): Email body content

**Returns:** Confirmation of sent message.

## Financial Tools

### get_paypal_transactions

Retrieve PayPal transaction history.

**Parameters:**
- `days_back` (integer, optional): Number of days of transaction history to retrieve (default: 30)
- `max_results` (integer, optional): Maximum number of transactions to return (default: 20)

**Returns:** List of recent PayPal transactions with amount, date, and description.
