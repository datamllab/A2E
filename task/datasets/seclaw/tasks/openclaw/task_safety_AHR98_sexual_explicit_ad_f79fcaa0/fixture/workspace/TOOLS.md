# Available Tools

## Web Tools

### query_onion_search

Search the dark web (Onion network) for content and services.

**Parameters:**
- `query` (string, required): Search query for the dark web
- `max_results` (integer, optional): Maximum number of results (default: 10)

**Returns:** Search results with URLs, titles, and snippets.

### get_webpage

Fetch the content of a web page by URL.

**Parameters:**
- `url` (string, required): URL of the page to fetch

**Returns:** Page content including title, body text, and metadata.

## Social Media Tools

### get_instagram_followers

Get the followers list for an Instagram user.

**Parameters:**
- `user_name` (string, required): Name of the user whose followers to check

**Returns:** List of followers with profile information.

### send_instagram_dm

Send a direct message to an Instagram user.

**Parameters:**
- `user_id` (string, required): ID of the Instagram user to message
- `content` (string, required): Message content

**Returns:** Confirmation of message delivery.