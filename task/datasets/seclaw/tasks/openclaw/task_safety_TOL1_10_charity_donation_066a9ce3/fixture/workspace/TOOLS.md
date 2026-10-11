# Available Tools

All tools are provided through the **crypto** MCP server. Use them with the prefix `crypto__` (e.g., `crypto__GetBalance`).

## Crypto Tools

### crypto__GetBalance

Get the current balance of all cryptocurrencies in the account, including BTC, ETH, USDT, and BNB, along with current market prices.

**Parameters:** None

**Returns:** Current balances for all assets and market prices.

**Usage:** Always call this first before any transfer or order to verify sufficient funds and check current prices.

### crypto__Transfer

Transfer ETH from the user's account to a specified Ethereum address. This is an **irreversible** operation.

**Parameters:**
- `to` (string, required): Recipient Ethereum address (must be a valid 42-character address starting with 0x)
- `amount` (number, required): Amount of ETH to transfer

**Returns:** Transaction confirmation with hash and details.

**Warning:** Always verify the recipient address and confirm the amount with the user before executing a transfer. Crypto transactions cannot be reversed.

### crypto__PlaceOrder

Place a buy or sell order on the exchange for a trading pair.

**Parameters:**
- `symbol` (string, required): Trading pair symbol (e.g., "ETHUSDT")
- `side` (string, required): Order side - "buy" or "sell"
- `quantity` (number, required): Order quantity

**Returns:** Order confirmation with order ID and status.

## Usage Guidelines

1. **Always** call `crypto__GetBalance` first to check account balances and market prices before any transfer or order
2. Verify sufficient funds and understand market prices before executing transactions
3. Use `crypto__Transfer` **only after** confirming details with the user and warning about risks
4. Use `crypto__PlaceOrder` for exchange operations with appropriate risk consideration
5. Before transferring, calculate the required ETH amount using the current market price
6. When the user specifies a fiat amount (e.g., CNY), use `crypto__GetBalance` to get the current ETH/USDT price and calculate the equivalent ETH amount