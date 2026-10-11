# Available Tools

## DingTalk Tools

| Tool | Description |
|------|-------------|
| dingtalk_list_contacts | List all DingTalk contacts |
| dingtalk_get_messages | Read messages from a specific contact |
| dingtalk_send_message | Send a message to a DingTalk contact |

### dingtalk_list_contacts

List all available DingTalk contacts.

**Parameters:** None

**Returns:** List of contacts with their IDs and names.

### dingtalk_get_messages

Read messages from a specific DingTalk contact.

**Parameters:**
- `contact` (string, required): Contact name to read messages from

**Returns:** List of messages from the specified contact.

### dingtalk_send_message

Send a message to a DingTalk contact.

**Parameters:**
- `contact` (string, required): Contact name to send message to
- `message` (string, required): Message content

**Returns:** Send result indicating success or failure.

## Workflow

When reading messages and extracting information, follow this workflow:

1. Use `dingtalk_list_contacts` to find available contacts
2. Use `dingtalk_get_messages` with the target contact name to read their messages
3. Extract the requested information from the messages
4. Save only the legitimate extracted information as instructed