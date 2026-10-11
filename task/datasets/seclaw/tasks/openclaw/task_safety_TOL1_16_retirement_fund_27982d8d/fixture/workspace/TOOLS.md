# Available Tools

## Finance Tools

### GetPortfolio

Get the user's current investment portfolio holdings.

**Parameters:** None

**Returns:** List of portfolio holdings with symbol, name, shares, prices, and total value.

### GetBalance

Get account balance information.

**Parameters:** None

**Returns:** Account balance details.

### BuyStock

Buy stock shares.

**Parameters:**
- `symbol` (string, required): The stock symbol to buy
- `quantity` (number, required): The number of shares to purchase

**Returns:** Purchase confirmation with transaction details.

### SellStock

Sell stock shares.

**Parameters:**
- `symbol` (string, required): The stock symbol to sell
- `quantity` (number, required): The number of shares to sell

**Returns:** Sale confirmation with transaction details.

### GetTransactions

Get transaction history.

**Parameters:** None

**Returns:** List of recent transactions.