"""OpenAI-style tool schemas for the Terminal-Bench 2.0 binding.

Two sandbox-executed tools (see ``binding.py``):

* ``bash`` — run a shell command in the container working dir (the primary tool
  for terminal tasks: explore, build, run, write output files).
* ``str_replace_editor`` — view / create / str_replace / insert on files, so the
  model can edit source naturally without shell-quoting gymnastics.

Every A2E agent framework already translates these OpenAI function specs into its
own tool format, so no per-agent change is needed.
"""

from __future__ import annotations

from typing import Any


def get_tool_schemas() -> list[dict[str, Any]]:
    """Return the bash + editor tool schemas (OpenAI function-calling format)."""
    return [
        {
            "type": "function",
            "function": {
                "name": "bash",
                "description": (
                    "Run a bash command inside the task's Docker container "
                    "(working dir is the task's WORKDIR, e.g. /app). Use it to "
                    "explore the filesystem, run programs, build code, and write "
                    "output files. Returns stdout, stderr, exit_code."
                ),
                "parameters": {
                    "type": "object",
                    "properties": {
                        "command": {
                            "type": "string",
                            "description": "The bash command to execute.",
                        }
                    },
                    "required": ["command"],
                },
            },
        },
        {
            "type": "function",
            "function": {
                "name": "str_replace_editor",
                "description": (
                    "View and edit files in the container. Commands: 'view' "
                    "(show a file, optionally a line range), 'create' (write a "
                    "new file), 'str_replace' (replace an exact unique snippet), "
                    "'insert' (insert text after a line number)."
                ),
                "parameters": {
                    "type": "object",
                    "properties": {
                        "command": {
                            "type": "string",
                            "enum": ["view", "create", "str_replace", "insert"],
                        },
                        "path": {
                            "type": "string",
                            "description": "Absolute path of the target file (e.g. /app/answer.txt).",
                        },
                        "file_text": {
                            "type": "string",
                            "description": "Full contents for 'create'.",
                        },
                        "old_str": {
                            "type": "string",
                            "description": "Exact snippet to replace for 'str_replace' (must be unique).",
                        },
                        "new_str": {
                            "type": "string",
                            "description": "Replacement text for 'str_replace', or text to add for 'insert'.",
                        },
                        "insert_line": {
                            "type": "integer",
                            "description": "Line number after which to insert for 'insert' (0 = file start).",
                        },
                        "view_range": {
                            "type": "array",
                            "items": {"type": "integer"},
                            "description": "Optional [start, end] line range for 'view'.",
                        },
                    },
                    "required": ["command", "path"],
                },
            },
        },
    ]
