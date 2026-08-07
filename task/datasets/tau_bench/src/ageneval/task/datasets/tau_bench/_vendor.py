"""Vendored τ-bench (v1, sierra-research/tau-bench) FULL tasks.

Loaded from ``full_tasks.json.gz`` — the complete τ-bench v1 ``tasks_test`` set
(retail + airline) extracted from the upstream repo, with real instructions and
real expected actions. Source: https://github.com/sierra-research/tau-bench (MIT).

``VENDOR_TASKS`` is grouped by domain (``{"retail": [...], "airline": [...]}``)
to preserve the domain-based loader/binding interface.
"""

from __future__ import annotations

import gzip
import json
from pathlib import Path

with gzip.open(Path(__file__).with_name("full_tasks.json.gz"), "rt", encoding="utf-8") as _fh:
    _DATA = json.load(_fh)

VENDOR_TOOL_NAMES: list[str] = _DATA["tool_names"]

VENDOR_TASKS: dict[str, list[dict]] = {}
for _t in _DATA["tasks"]:
    VENDOR_TASKS.setdefault(_t.get("domain", "retail"), []).append(_t)
