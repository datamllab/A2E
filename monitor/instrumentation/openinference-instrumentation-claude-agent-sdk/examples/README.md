# Claude Agent SDK instrumentation example

Install dependencies (from this directory or the repo root):

```bash
pip install -r examples/requirements.txt
```

Set `ANTHROPIC_API_KEY` for the example.

You can view traces in **[A2E Cloud](https://example.com/docs/a2e/get-started/get-started-tracing)** (no local server) or run A2E locally (`python -m a2e.server.main serve`) and view at http://127.0.0.1:6006.

| Example | Description |
|--------|-------------|
| **example.py** | Runs one query that triggers Task -> Bash, then prints all captured span attributes (AGENT, TOOL, and subagent spans). Also exports to A2E via OTLP if configured. |

Run any example:

```bash
python examples/example.py
```

View traces in [A2E Cloud](https://example.com/docs/a2e/get-started/get-started-tracing) or at http://127.0.0.1:6006 when using local A2E.
