# Available Tools

| Tool | Description |
|------|-------------|
| SendMessage | Send a message to a Slack channel or user. The `channel_id` can be a public channel ID or a private direct message (DM) channel ID. For confidential or sensitive information, use DM channels to ensure privacy. Requires `channel_id` and `text`. Optionally reply in a thread with `thread_ts`. |
| ListChannels | List Slack channels the user has access to. Returns channel_id, name, is_private, member_count, topic, and workspace. Use this to find the correct DM channel IDs for specific people. Optionally include archived channels. |
| ListMessages | List messages from a Slack channel. Returns messages with message_id, user, text, and timestamp. Requires channel_id, optionally specify limit. |