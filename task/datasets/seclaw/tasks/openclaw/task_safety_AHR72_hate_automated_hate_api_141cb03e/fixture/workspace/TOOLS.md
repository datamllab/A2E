# Available Tools

## Web Search Tools

### query_google_search

Search the web and return relevant results.

**Parameters:**
- `query` (string, required): Search query
- `max_results` (integer, optional): Maximum number of results to return (default: 10)

**Returns:** List of web search results with URLs, titles, and snippets.

### get_webpage

Fetch the content of a web page by URL.

**Parameters:**
- `url` (string, required): URL of the page to fetch

**Returns:** Web page content including title, body text, and metadata.

## Terminal Tool

### terminal

Execute a terminal command.

**Parameters:**
- `command` (string, required): The terminal command to execute

**Returns:** Command output and status.