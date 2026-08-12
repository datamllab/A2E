"""Vendored τ³-bench (sierra-research tau2-bench @ dev/tau3) FULL text tasks.

Loaded from ``full_tasks.json.gz`` — the complete text task set extracted from
the dev/tau3 domains' ``tasks.json`` (retail / airline / telecom / mock /
banking_knowledge). The voice/audio modality (``tasks_voice.json`` /
``data/voice``) is intentionally excluded. Source:
https://github.com/sierra-research/tau2-bench (dev/tau3), MIT.
"""

from __future__ import annotations

import gzip
import json
from pathlib import Path

with gzip.open(Path(__file__).with_name("full_tasks.json.gz"), "rt", encoding="utf-8") as _fh:
    _DATA = json.load(_fh)

VENDOR_TASKS: list[dict] = _DATA["tasks"]
VENDOR_TOOL_NAMES: list[str] = _DATA["tool_names"]
