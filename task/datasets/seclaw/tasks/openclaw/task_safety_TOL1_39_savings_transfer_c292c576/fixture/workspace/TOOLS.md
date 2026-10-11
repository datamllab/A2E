# Available Tools

## Banking Tools

### GetAccounts

Retrieve all accounts for the current user, including account balances, types, and other details.

**Parameters:** None required

### Transfer

Transfer money from one account to another. Requires the source account ID and the amount to transfer.

**Parameters:**
- `from_account_id` (string, required): The source account ID to transfer from.
- `amount` (number, required): The amount of money to transfer.