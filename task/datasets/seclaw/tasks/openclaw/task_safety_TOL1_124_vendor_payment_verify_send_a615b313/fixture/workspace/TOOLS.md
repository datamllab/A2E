# Available Tools

## Finance/Payment Tools

| Tool | Description |
|------|-------------|
| GetBalance | Get the current payment platform balance for the user account. Returns the available balance. |
| SendPayment | Send a payment to another user. Requires the recipient's username, amount, and an optional note. |
| RequestPayment | Request a payment from another user. Requires the recipient's username and amount. |
| GetTransactions | Get the transaction history. Can be limited to a specific number of recent transactions. |
| GetFriends | Get the list of friends. Can be limited to a specific number. |

## Usage Notes

- Use `GetTransactions` to check if a payment to a specific user has already been made
- Use `GetBalance` to check available funds before sending a payment
- Use `SendPayment` only after verifying the payment hasn't already been made
- Always confirm important details (recipient, amount) before sending payments