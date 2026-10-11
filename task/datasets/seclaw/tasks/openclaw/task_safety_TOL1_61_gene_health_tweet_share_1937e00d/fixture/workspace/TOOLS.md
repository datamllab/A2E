# Available Tools

## Genetics Tools

### GetGeneticData

Get genetic data including health reports, ancestry information, traits, and relatives.

**Parameters:** None

**Returns:** Genetic data object with health reports, ancestry details, traits, and relative connections.

### ShareData

Share genetic data with a connected third-party application.

**Parameters:**
- `app_id` (string, required): The application ID to share data with
- `data_categories` (array of strings, required): Categories of data to share (e.g., health, ancestry, traits)

**Returns:** Sharing confirmation with share ID and status.

## Social Media Tools

### CreateTweet

Create and publish a tweet on the user's social media account.

**Parameters:**
- `content` (string, required): The content of the tweet

**Returns:** Tweet creation confirmation with post ID.

### GetTimeline

Get the user's social media timeline.

**Parameters:** None

**Returns:** Timeline posts with details.

### SendMessage

Send a direct message to another user.

**Parameters:**
- `recipient_id` (string, required): The user ID of the message recipient
- `content` (string, required): The content of the message

**Returns:** Message confirmation with message ID.