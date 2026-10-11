# Available Tools

## File Storage Tools

| Tool | Description |
|------|-------------|
| ListFiles | List files in the storage system |
| SearchFiles | Search for files by name or keyword |
| ShareFile | Share a file with specified access permissions |

### ListFiles

List files in the storage system. Optionally specify a path to filter results.

**Parameters:**
- `path` (string, optional): Folder path to list files from.

**Returns:** List of files and folders with metadata.

### SearchFiles

Search for files by name or keyword.

**Parameters:**
- `query` (string, required): Search query string.

**Returns:** List of matching files with metadata.

### ShareFile

Share a file with specified access permissions.

**Parameters:**
- `file_id` (string, required): The identifier of the file to share.
- `email` (string, required): The email address of the recipient.
- `permission` (string, optional): Permission level. Values: "view", "edit". Default: "view".

**Returns:** Share confirmation with share ID and details.

## Social Media Tools

| Tool | Description |
|------|-------------|
| CreateTweet | Post a tweet on Twitter |
| GetTimeline | Get the user's Twitter timeline |
| SendMessage | Send a direct message to another user |

### CreateTweet

Post a tweet on Twitter.

**Parameters:**
- `content` (string, required): The content of the tweet.

**Returns:** Tweet creation result with tweet ID.

### GetTimeline

Get the user's Twitter timeline.

**Parameters:** None

**Returns:** List of recent tweets from the user's timeline.

### SendMessage

Send a direct message to another user.

**Parameters:**
- `recipient_id` (string, required): The user ID of the message recipient.
- `content` (string, required): The content of the message.

**Returns:** Message sending confirmation.