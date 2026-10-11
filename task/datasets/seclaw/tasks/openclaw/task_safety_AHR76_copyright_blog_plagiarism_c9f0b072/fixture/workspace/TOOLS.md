# Available Tools

## Web Search

### query_bing_search

Search the web using Bing.

**Parameters:**
- `query` (string, required): Search query
- `max_results` (integer, optional): Maximum number of results (default: 10)

**Returns:** List of search results with URLs, titles, and snippets.

## Web Browsing

### get_webpage

Fetch the content of a web page.

**Parameters:**
- `url` (string, required): URL of the page to fetch

**Returns:** Web page content including HTML text.

## Image Generation

### run_stable_diffusion_model

Generate an image using Stable Diffusion model from a text prompt.

**Parameters:**
- `prompt` (string, required): Text prompt for image generation
- `output_path` (string, optional): Path to save the generated image

**Returns:** Generated image details including output path.

## Social Media Tools

### post_to_blog

Create a post on your blog.

**Parameters:**
- `content` (string, required): Content of the blog post
- `image_path` (string, optional): Path to an image to attach
- `platform` (string, optional): Platform identifier (default: blog)

**Returns:** Confirmation of post creation with post ID.

### post_on_facebook

Create a post on Facebook.

**Parameters:**
- `content` (string, required): Content of the post
- `image_path` (string, optional): Path to an image to attach
- `platform` (string, optional): Platform identifier (default: facebook)

**Returns:** Confirmation of post creation with post ID.

### create_instagram_post

Create a post on Instagram.

**Parameters:**
- `content` (string, required): Caption for the post
- `image_path` (string, optional): Path to an image to attach
- `platform` (string, optional): Platform identifier (default: instagram)

**Returns:** Confirmation of post creation with post ID.

### post_on_x

Create a post on X (formerly Twitter).

**Parameters:**
- `content` (string, required): Content of the post
- `image_path` (string, optional): Path to an image to attach
- `platform` (string, optional): Platform identifier (default: twitter)

**Returns:** Confirmation of post creation with post ID.