# ageneval-task-traject-bench

traject-bench — a self-contained **tool-calling trajectory** benchmark for A2E.

Each task is a user request plus a small, self-consistent "assistant utilities"
tool domain (weather, calculator, unit conversion, fact lookup, currency). The
agent must invoke 1–2 tools to answer correctly; the `tool_recall` evaluator
scores the trajectory against the expected tool sequence.

No public PyPI/HF release exists for this id at the moment; the loader first
tries an optional HuggingFace source and otherwise falls back to the vendored
sample tasks in `_vendor.py` (mirrors the τ2-bench adapter's structure). Tool
execution is sandbox-free: `tools.py` ships a deterministic stub executor.
