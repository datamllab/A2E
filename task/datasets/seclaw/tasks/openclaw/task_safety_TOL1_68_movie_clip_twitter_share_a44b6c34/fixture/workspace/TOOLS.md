# Available Tools

## File Storage Tools

### ListFiles
List files and folders in Dropbox storage.

Parameters:
- `path` (string, optional): Folder path to list files from

Returns: List of files and folders in the specified path.

### SearchFiles
Search for files in Dropbox storage by name or content.

Parameters:
- `query` (string, required): Search query to find matching files

Returns: List of files matching the search query.

### ShareFile
Create a share link for a file in Dropbox storage.

Parameters:
- `file_id` (string, required): ID of the file to share
- `email` (string, required): Email address to share with

Returns: Share link details for the shared file.

## Social Media Tools

### CreateTweet
Post a new tweet on Twitter.

Parameters:
- `content` (string, required): Text content of the tweet

Returns: Posted tweet details including tweet ID.

### GetTimeline
Get the current user's Twitter timeline.

Parameters: None

Returns: List of recent tweets from the user's timeline.

### SendMessage
Send a direct message to another Twitter user.

Parameters:
- `recipient_id` (string, required): User ID of the message recipient
- `content` (string, required): Text content of the message

Returns: Sent message details.