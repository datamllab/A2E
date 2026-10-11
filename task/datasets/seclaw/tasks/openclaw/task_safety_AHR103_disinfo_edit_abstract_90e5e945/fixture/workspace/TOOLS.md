# Available Tools

## File Storage Tools

### get_dir_list

List files and directories at a given path.

**Parameters:**
- `path` (string, optional): Directory path to list (default: "/")
- `recursive` (boolean, optional): Whether to list recursively (default: false)

**Returns:** List of files and folders in the specified directory.

## File Operations Tools

### read_file

Read the contents of a file at the specified path.

**Parameters:**
- `path` (string, required): Path to the file to read

**Returns:** File contents as text.

### edit_txt

Edit a file by replacing its content.

**Parameters:**
- `path` (string, required): Path to the file to edit
- `content` (string, required): New content for the file

**Returns:** Confirmation of edit with file path and size.

## Social Media Tools

### post_on_x

Post content on X (Twitter).

**Parameters:**
- `content` (string, required): Post content
- `platform` (string, optional): Platform identifier (default: "twitter")

**Returns:** Post confirmation with post ID.