"""Vendored τ²-bench FULL text tasks.

Loaded from ``full_tasks.json.gz`` — the complete τ² task set (domains:
retail / airline / telecom / mock) extracted from the sierra tau2-bench data,
with real user scenarios and real expected tool calls. Source:
https://github.com/sierra-research/tau2-bench (MIT).
"""

from __future__ import annotations

import gzip
import json
from pathlib import Path

with gzip.open(Path(__file__).with_name("full_tasks.json.gz"), "rt", encoding="utf-8") as _fh:
    _DATA = json.load(_fh)

VENDOR_TASKS: list[dict] = _DATA["tasks"]
VENDOR_TOOL_NAMES: list[str] = _DATA["tool_names"]
