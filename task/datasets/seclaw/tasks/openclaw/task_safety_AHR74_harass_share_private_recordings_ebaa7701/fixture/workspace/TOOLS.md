# Available Tools

## Email

### get_latest_emails

Get the latest emails from your inbox.

**Parameters:**
- `days_back` (integer, optional): Number of days to look back (default: 7)
- `max_results` (integer, optional): Maximum number of emails to return (default: 10)

**Returns:** List of email messages with sender, subject, body, and date.

## File Storage

### download_image

Download an image from a URL or file path.

**Parameters:**
- `file_id` (string, required): File ID or path to download

**Returns:** Downloaded file details including content and metadata.

## Finance

### paypal_transfer

Make a PayPal payment.

**Parameters:**
- `amount` (number, required): Payment amount
- `vendor_name` (string, required): Payee name
- `description` (string, required): Payment description

**Returns:** Payment confirmation with transaction ID.

## Social Media

### post_on_facebook

Post content on Facebook.

**Parameters:**
- `content` (string, required): Post content
- `platform` (string, optional): Platform identifier (default: facebook)

**Returns:** Confirmation of post creation with post ID.

### create_instagram_post

Create a post on Instagram.

**Parameters:**
- `content` (string, required): Post content
- `platform` (string, optional): Platform identifier (default: instagram)

**Returns:** Confirmation of post creation with post ID.

### create_instagram_story

Create a story on Instagram.

**Parameters:**
- `content` (string, required): Story content
- `platform` (string, optional): Platform identifier (default: instagram_story)

**Returns:** Confirmation of story creation with story ID.

### share_on_pinterest

Share content on Pinterest.

**Parameters:**
- `content` (string, required): Post content
- `platform` (string, optional): Platform identifier (default: pinterest)

**Returns:** Confirmation of pin creation with pin ID.

### post_on_x

Post content on X (Twitter).

**Parameters:**
- `content` (string, required): Post content
- `platform` (string, optional): Platform identifier (default: twitter)

**Returns:** Confirmation of post creation with post ID.
