# A2E Examples

A single bash script that walks through the complete A2E workflow: setup, experiments, and evaluation.

## Prerequisites

- Python 3.10+
- `uv` package manager
- Docker (sandbox section only)

```bash
cd task && uv sync --frozen --all-packages --index-strategy unsafe-best-match
cd server && uv sync
cd eval && uv sync
```

## Quick Run

```bash
# Terminal 1 — start the server
cd server && uv run a2e serve

# Terminal 2 — follow the walkthrough
cd task
set -a; . ../.env; set +a
bash ../example/run_examples.sh
```
The script pauses after each step so you can inspect results at http://localhost:6006.
Press Enter to continue to the next section.
