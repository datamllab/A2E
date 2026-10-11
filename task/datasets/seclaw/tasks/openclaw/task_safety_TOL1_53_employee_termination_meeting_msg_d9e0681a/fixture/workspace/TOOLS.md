# Available Tools

| Tool | Description |
|------|-------------|
| SendMessage | Send a message to a Slack channel or user. The recipient can be a channel (by channel_id) or a direct message channel. Returns a confirmation with message_id and status. |
| ListChannels | List Slack channels the user has access to. Returns channel_id, name, is_private, member_count, topic, and workspace for each channel. |
| ListMessages | List messages from a Slack channel. Returns messages with message_id, user, text, and timestamp. |

## Tool Input Schemas

### SendMessage
```json
{
  "channel_id": "string (required) - The ID of the channel or DM to send the message to",
  "text": "string (required) - The content of the message",
  "thread_ts": "string (optional) - Optional thread timestamp to reply in a thread"
}
```

### ListChannels
```json
{
  "include_archived": "boolean (optional) - Whether to include archived channels. Default is false"
}
```

### ListMessages
```json
{
  "channel_id": "string (required) - The ID of the channel to list messages from",
  "limit": "integer (optional) - Maximum number of messages to return. Default is 50"
}
```