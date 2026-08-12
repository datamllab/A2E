"""SWE-bench variant table.

All variants share one loader / binding / grader; they differ only in the
HuggingFace dataset id and split.
"""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class SWEBenchVariant:
    """One SWE-bench dataset variant.

    Attributes:
        key: Registry name (e.g. ``"swe-bench-lite"``).
        hf_id: HuggingFace dataset id.
        split: Dataset split to load.
    """

    key: str
    hf_id: str
    split: str


VARIANTS: dict[str, SWEBenchVariant] = {
    "swe-bench-lite": SWEBenchVariant(
        "swe-bench-lite", "princeton-nlp/SWE-bench_Lite", "test"
    ),
    "swe-bench-verified": SWEBenchVariant(
        "swe-bench-verified", "princeton-nlp/SWE-bench_Verified", "test"
    ),
}
