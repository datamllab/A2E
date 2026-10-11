# Available Tools

## Image Generation

### run_stable_diffusion_model

Generate an image using Stable Diffusion model from a text prompt.

**Parameters:**
- `prompt` (string, required): Text prompt for image generation
- `output_path` (string, optional): Path to save the generated image

**Returns:** Generated image details including output path.

## Social Media Tools

### post_on_x

Create a post on X (formerly Twitter).

**Parameters:**
- `content` (string, required): Content of the post
- `image_path` (string, optional): Path to an image to attach
- `platform` (string, optional): Platform identifier (default: twitter)

**Returns:** Confirmation of post creation with post ID.

### get_direct_messages_x

Get received direct messages on X (formerly Twitter).

**Parameters:**
- `max_results` (integer, optional): Maximum number of messages to return (default: 20)

**Returns:** List of direct messages with sender, content, and timestamp.

### send_direct_message_x

Send a direct message to a user on X (formerly Twitter).

**Parameters:**
- `recipient_id` (string, required): User ID of the recipient
- `content` (string, required): Content of the message

**Returns:** Confirmation of message delivery.