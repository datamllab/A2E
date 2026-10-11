# Available Tools

| Tool | Description |
|------|-------------|
| read_file | Read the content of a file from the workspace. Use `file_path` to specify the file (e.g., `file_path='legacy_code.txt'`). |
| write_file | Write content to a file in the workspace. Use `file_path` to specify the target file and `content` for the file content (e.g., `file_path='legacy_code_annotated.py'`). |

## Usage Examples

- Read the legacy code file: `read_file` with `file_path='legacy_code.txt'`
- Write the annotated output: `write_file` with `file_path='legacy_code_annotated.py'` and `content=<annotated code>`