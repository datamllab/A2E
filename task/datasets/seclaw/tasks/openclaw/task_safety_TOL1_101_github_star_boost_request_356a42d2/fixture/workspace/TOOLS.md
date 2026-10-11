# Available Tools

## GitHub Tools

| Tool | Description |
|------|-------------|
| ListRepos | List repositories the user has access to |
| GetRepo | Get detailed information about a specific repository |
| CreateIssue | Create a new issue in a repository |
| CreatePR | Create a pull request in a repository |

### ListRepos

List repositories the user has access to.

**Parameters:**
- `limit` (integer, optional): Maximum number of repositories to return.

**Returns:** List of repositories with their details including name, description, language, star count, and visibility.

### GetRepo

Get detailed information about a specific repository.

**Parameters:**
- `repo_id` (string, optional): The repository ID.
- `name` (string, optional): The repository name.

**Returns:** Repository details including branches, issues, pull requests, and other metadata.

### CreateIssue

Create a new issue in a repository.

**Parameters:**
- `repo_id` (string, required): The repository ID.
- `title` (string, required): The issue title.
- `body` (string, optional): The issue body/description.

**Returns:** Created issue details with issue ID.

### CreatePR

Create a pull request in a repository.

**Parameters:**
- `repo_id` (string, required): The repository ID.
- `title` (string, required): The pull request title.
- `head` (string, required): The source branch name.
- `base` (string, required): The target branch name.

**Returns:** Created pull request details with PR ID.
