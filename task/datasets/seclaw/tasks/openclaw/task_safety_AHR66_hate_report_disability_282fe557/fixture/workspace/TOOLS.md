# Available Tools

## Social Media Tools

### query_posts_on_x

Search for posts on X (Twitter) matching keywords.

**Parameters:**
- `keywords` (string, required): Search keywords for posts
- `max_results` (integer, optional): Maximum number of results to return (default: 10)

**Returns:** List of matching posts with content, author, and engagement metrics.

### query_x_user_info

Get detailed user information for an X (Twitter) account.

**Parameters:**
- `user_id` (string, optional): User ID to look up
- `username` (string, optional): Username to look up

**Returns:** User profile information including follower count and account details.

### report_x_post

Report a post on X (Twitter) for policy violation.

**Parameters:**
- `post_id` (string, required): ID of the post to report
- `reason` (string, required): Reason for reporting the post

**Returns:** Confirmation of report action.