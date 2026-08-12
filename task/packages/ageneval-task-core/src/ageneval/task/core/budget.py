"""Shared LLM / loop budget so every harness calls the API with the same caps.

Fair comparison requires the same ``max_tokens``, turn/step budget, and
request timeout on every agent. Dataset ``agent_overrides`` (τ=30,
DeepSearchQA=20, sandbox=40) still apply equally to all harnesses.
"""

from __future__ import annotations

import os


def max_tokens() -> int:
    return int(os.environ.get("A2E_MAX_TOKENS", "4096"))


def max_turns() -> int:
    return int(os.environ.get("A2E_MAX_TURNS", os.environ.get("A2E_MAX_STEPS", "8")))


def max_steps() -> int:
    return int(os.environ.get("A2E_MAX_STEPS", os.environ.get("A2E_MAX_TURNS", "8")))


def llm_timeout() -> float:
    return float(os.environ.get("A2E_LLM_TIMEOUT", "180"))


def run_deadline() -> float:
    """Whole-agent wall clock. Same value for every harness on a dataset.

    ``run_n1.sh`` sets ``A2E_RUN_DEADLINE`` (DeepSearchQA=1700, τ=1100, QA=600)
    so Agno cannot stop at 600s while others keep going to 1800s.
    """
    return float(
        os.environ.get(
            "A2E_RUN_DEADLINE",
            os.environ.get("A2E_AGNO_DEADLINE", "1800"),
        )
    )
