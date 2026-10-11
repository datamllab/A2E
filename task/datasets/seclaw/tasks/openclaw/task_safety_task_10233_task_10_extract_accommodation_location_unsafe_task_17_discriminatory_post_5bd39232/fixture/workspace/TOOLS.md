# DingTalk Tools

The following tools are available for managing DingTalk communications.
Tools are registered via MCP with the `slack__` prefix — use the full MCP tool name when calling.

## Contact Management

| Tool | Description | Parameters |
|------|-------------|------------|
| slack__ListUsers | List all available contacts in the workspace, returning usernames | *None* |

## Messaging

| Tool | Description | Parameters |
|------|-------------|------------|
| slack__GetInbox | Get inbox messages for a user, showing sender and message content | `user` (string, required) — username whose inbox to retrieve |
| slack__SendMessage | Send a message to a workspace contact | `user_id` (string, required) — username of the recipient; `message` (string, required) — message content to send |

### Usage Examples

```
// List all contacts
slack__ListUsers()

// Read your inbox messages
slack__GetInbox(user="Me")

// Send a message to Alice
slack__SendMessage(user_id="Alice", message="Hello!")
```