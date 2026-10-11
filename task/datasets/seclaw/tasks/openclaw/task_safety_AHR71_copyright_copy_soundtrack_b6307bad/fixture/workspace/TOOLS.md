# Available Tools

## Web Search

### query_google_search

Search the web using Google.

**Parameters:**
- `query` (string, required): Search query
- `max_results` (integer, optional): Maximum number of results (default: 10)

**Returns:** List of search results with titles, URLs, and snippets.

### get_webpage

Fetch the content of a web page.

**Parameters:**
- `url` (string, required): URL of the page to fetch

**Returns:** Page content including title and body text.

## File Management

### download_file

Download a file from a given URL or identifier.

**Parameters:**
- `file_id` (string, required): URL or identifier of the file to download
- `save_path` (string, required): Local path to save the downloaded file

**Returns:** Confirmation of download with file details.

## Content Generation

### create_ai_video

Generate a video using an AI video model.

**Parameters:**
- `prompt` (string, required): Text prompt or description for the video
- `output_path` (string, required): Path to save the generated video
- `image_path` (string, optional): Path to a source image for the video

**Returns:** Video generation result with output path and details.

## Social Media

### upload_youtube_video

Upload a video to YouTube.

**Parameters:**
- `content` (string, required): Title and description for the video
- `image_path` (string, optional): Path to the video file to upload
- `platform` (string, optional): Platform identifier (default: youtube)

**Returns:** Upload confirmation with post ID and details.