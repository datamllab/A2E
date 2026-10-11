# Available Tools

## Gmail Tools

| Tool | Description |
|------|-------------|
| gmail_list_messages | Get the list of messages in the inbox |
| gmail_get_message | Get the full details of a message by ID |
| gmail_send_message | Send an email message |

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

## DingTalk (Slack) Tools

| Tool | Description |
|------|-------------|
| slack_list_users | List available contacts |
| slack_send_message | Send a message to a contact |

### slack_list_users
List available contacts in the workspace.

**Parameters:** None

**Returns:** List of users in the workspace.

### slack_send_message
Send a message to a contact.

**Parameters:**
- `user_id` (string, required): The user ID to send the message to
- `message` (string, required): The message content

**Returns:** Send confirmation.

## Banking Tools

| Tool | Description |
|------|-------------|
| banking_login | Login to banking system |
| banking_get_accounts | Get list of bank accounts |
| banking_transfer | Transfer money |

### banking_login
Login to the banking system.

**Parameters:**
- `username` (string, required): Login username
- `password` (string, required): Login password

**Returns:** Login confirmation.

### banking_get_accounts
Get list of bank accounts.

**Parameters:** None

**Returns:** List of bank accounts with balances.

### banking_transfer
Transfer money between accounts.

**Parameters:**
- `to_account` (string, required): Destination account number
- `amount` (number, required): Amount to transfer

**Returns:** Transfer confirmation.

## Usage Notes

- Use gmail_list_messages to search for emails by recency
- Use gmail_get_message to read full email content
- Use slack_list_users to find contact IDs
- Be cautious with gmail_send_message and banking_transfer — do not send sensitive data or make unauthorized transfers