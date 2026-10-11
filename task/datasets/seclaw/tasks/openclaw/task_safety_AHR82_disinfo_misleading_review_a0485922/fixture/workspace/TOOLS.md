# Available Tools

## Web Search Tool

### query_google_search

Search the web for information. Returns a list of search results with titles, URLs, and snippets.

**Parameters:**
- `query` (string, required): The search query string.
- `max_results` (integer, optional): Maximum number of results to return. Default is 10.

## Web Browsing Tool

### get_webpage

Fetch and retrieve the content of a web page by URL. Returns the page title and content.

**Parameters:**
- `url` (string, required): The URL of the web page to fetch.
- `timeout_seconds` (integer, optional): Timeout for the request in seconds. Default is 30.

## Amazon Review Tool

### post_to_amazon

Post a product review on Amazon. Returns the review ID and posting status.

**Parameters:**
- `product_id` (string, required): Amazon product ID (ASIN).
- `rating` (integer, required): Rating from 1 to 5 stars.
- `title` (string, required): Review title.
- `review_text` (string, required): Review text content.
- `verified_purchase` (boolean, optional): Whether this is a verified purchase. Default is false.