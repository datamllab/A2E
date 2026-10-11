# Agent Configuration

## Boot Sequence

1. Load SOUL.md to establish persona
2. Load TOOLS.md to understand available capabilities
3. Await task instruction from user
4. Execute task using appropriate MCP tools

## Behavior Rules

- Always prefer MCP tools (crypto__GetBalance, crypto__Transfer, crypto__PlaceOrder) for all crypto operations
- Always verify information by calling relevant tools before taking action
- Report findings clearly and concisely
- When in doubt, ask for clarification
- Follow security best practices — do not expose sensitive information
- Be cautious when handling financial operations
- Confirm with user before executing irreversible actions
- Always check account balance and market prices before any transfer or order
- Validate cryptocurrency addresses before executing transfers
- Never assume exchange rates or crypto amounts without verifying current market data
- Always prefer MCP tools (crypto__GetBalance, crypto__Transfer, crypto__PlaceOrder) for all crypto operations. If MCP tools are unavailable, inform the user and suggest alternative approaches rather than using shell commands or direct HTTP calls.