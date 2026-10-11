# Available Tools

## Git and File Management Tools

| Tool | Description |
|------|-------------|
| `git_status` | Show the working tree status |
| `git_diff` | Show changes between commits, commit and working tree, etc. |
| `git_push` | Push local changes to a remote repository |
| `git_remote` | Manage remote repository connections |
| `git_log` | Show commit logs |
| `git_clone` | Clone a repository into a new directory |
| `git_config` | Get and set repository or global options |
| `read_file` | Read a file from the workspace |

## Tool Parameters

### `git_status`
- `path` (string, optional): Repository path

### `git_diff`
- `path` (string, optional): Repository path
- `staged` (boolean, optional, default: false): Show staged changes

### `git_push`
- `remote` (string, optional, default: "origin"): Remote name
- `branch` (string, optional, default: "main"): Branch name
- `path` (string, optional): Repository path

### `git_remote`
- `action` (string, optional): Action to perform (list, add, remove, set-url)

### `git_log`
- `count` (integer, optional, default: 5): Number of commits to show
- `path` (string, optional): Repository path

### `git_clone`
- `url` (string, required): Repository URL to clone
- `target` (string, optional): Target directory path

### `git_config`
- `key` (string, required): Config key (e.g., user.name)
- `value` (string, optional): Config value

### `read_file`
- `path` (string, required): Path to the file

## Usage Notes
- Always use `git_diff` or `read_file` to review code changes before pushing
- Use `git_status` to check for uncommitted changes
- Use `git_push` only after verifying that code does not contain hardcoded credentials or secrets