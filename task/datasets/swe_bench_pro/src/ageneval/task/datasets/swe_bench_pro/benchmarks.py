"""SWE-bench Pro variant table.

One public variant — the open ``ScaleAI/SWE-bench_Pro`` test split (731 long-
horizon software-engineering instances across professional OSS repos). All
variants share one loader / binding / grader; they differ only in the
HuggingFace dataset id and split.
"""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class SWEBenchProVariant:
    """One SWE-bench Pro dataset variant.

    Attributes:
        key: Registry name (e.g. ``"swe-bench-pro"``).
        hf_id: HuggingFace dataset id.
        split: Dataset split to load.
    """

    key: str
    hf_id: str
    split: str


VARIANTS: dict[str, SWEBenchProVariant] = {
    "swe-bench-pro": SWEBenchProVariant(
        "swe-bench-pro", "ScaleAI/SWE-bench_Pro", "test"
    ),
}
