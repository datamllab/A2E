"""Registries of available datasets / agents / evaluators.

This is the **single source of truth** that the CLI (`task/examples/run_experiment.py`)
and any future UI (A2E REST + React form) consult to populate dropdowns.

Adding a new dataset, agent or evaluator means inserting one line here.
"""

from __future__ import annotations

import json
import os
import re
from typing import Any, Callable, Dict

from ageneval.task.core.instrumentation import Framework

# ─── DATASETS ────────────────────────────────────────────────────────────────
# Each entry: name → (loader fn, binding fn). Loader returns Dataset; binding
# returns AgentBinding (consumed by agents).


def _load_tau_bench(**kw: Any):
    from ageneval.task.datasets.tau_bench import load_tau_bench_tasks
    return load_tau_bench_tasks(**kw)


def _bind_tau_bench(**kw: Any):
    from ageneval.task.datasets.tau_bench import build_tau_bench_binding
    return build_tau_bench_binding(**kw)


def _load_tau2(**kw: Any):
    from ageneval.task.datasets.tau2 import load_tau2_tasks
    return load_tau2_tasks(**kw)


def _bind_tau2(**kw: Any):
    from ageneval.task.datasets.tau2 import build_tau2_binding
    return build_tau2_binding(domain=kw.get("domain") or "retail")


def _load_tau3(**kw: Any):
    from ageneval.task.datasets.tau3 import load_tau3_tasks
    allowed = {k: v for k, v in kw.items() if k in ("n", "split", "domain")}
    return load_tau3_tasks(**allowed)


def _bind_tau3(**kw: Any):
    from ageneval.task.datasets.tau3 import build_tau3_binding
    return build_tau3_binding(domain=kw.get("domain") or "retail")


def _load_mmlu(**kw: Any):
    from ageneval.task.datasets.mmlu import load_mmlu_tasks
    return load_mmlu_tasks(**kw)


def _bind_mmlu(**_kw: Any):
    from ageneval.task.datasets.mmlu import build_mmlu_binding
    return build_mmlu_binding()


def _load_gsm8k(**kw: Any):
    from ageneval.task.datasets.gsm8k import load_gsm8k_tasks
    return load_gsm8k_tasks(**kw)


def _bind_gsm8k(**_kw: Any):
    from ageneval.task.datasets.gsm8k import build_gsm8k_binding
    return build_gsm8k_binding()


def _load_humaneval(**kw: Any):
    from ageneval.task.datasets.humaneval import load_humaneval_tasks
    return load_humaneval_tasks(**kw)


def _bind_humaneval(**_kw: Any):
    from ageneval.task.datasets.humaneval import build_humaneval_binding
    return build_humaneval_binding()


def _load_persistbench(**kw: Any):
    from ageneval.task.datasets.persistbench import load_persistbench_tasks
    return load_persistbench_tasks(**kw)


def _bind_persistbench(**_kw: Any):
    from ageneval.task.datasets.persistbench import build_persistbench_binding
    return build_persistbench_binding()


def _load_traject_bench(**kw: Any):
    from ageneval.task.datasets.traject_bench import load_traject_bench_tasks
    return load_traject_bench_tasks(**{k: v for k, v in kw.items() if k in ("n", "split")})


def _bind_traject_bench(**_kw: Any):
    from ageneval.task.datasets.traject_bench import build_traject_bench_binding
    return build_traject_bench_binding()


def _load_gdpval(**kw: Any):
    from ageneval.task.datasets.gdpval import load_gdpval_tasks
    return load_gdpval_tasks(**{k: v for k, v in kw.items() if k in ("n", "split")})


def _bind_gdpval(**_kw: Any):
    from ageneval.task.datasets.gdpval import build_gdpval_binding
    return build_gdpval_binding()


def _load_deepsearchqa(**kw: Any):
    from ageneval.task.datasets.deepsearchqa import load_deepsearchqa_tasks
    return load_deepsearchqa_tasks(**{k: v for k, v in kw.items() if k in ("n", "split")})


def _bind_deepsearchqa(**_kw: Any):
    from ageneval.task.datasets.deepsearchqa import build_deepsearchqa_binding
    return build_deepsearchqa_binding()


# ─── sandbox datasets (SWE-bench) ─────────────────────────────────────────────
# These have kind="sandbox": the runner wraps the agent in a SandboxScoringRunner
# (see task_fn in run_experiment.py / a2e.py) which spins up the per-task
# container, lets the agent edit code, then grades with score_swe_bench.


def _load_swe(variant: str) -> Callable:
    def _f(**kw: Any):
        from ageneval.task.datasets.swe_bench import load_swe_bench_tasks
        kw = dict(kw)
        # Optionally pin a specific instance via A2E_SWE_INSTANCE so a demo / test
        # run targets an already-pulled image instead of fetching a random
        # multi-GB one. Explicit instance_ids (e.g. from the test harness) win.
        if not kw.get("instance_ids"):
            _pin = os.environ.get("A2E_SWE_INSTANCE")
            if _pin:
                kw["instance_ids"] = [_pin]
        return load_swe_bench_tasks(
            variant, **{k: v for k, v in kw.items() if k in ("n", "split", "instance_ids")}
        )
    return _f


def _bind_swe(**_kw: Any):
    from ageneval.task.datasets.swe_bench import build_swe_bench_binding
    return build_swe_bench_binding()


def _score_swe(task: Any, sandbox: Any, model_patch: str) -> Any:
    from ageneval.task.datasets.swe_bench import score_swe_bench
    return score_swe_bench(task, sandbox, model_patch)


def _setup_swe(task: Any, sandbox: Any) -> None:
    from ageneval.task.datasets.swe_bench import setup_swe_bench
    return setup_swe_bench(task, sandbox)


# ─── SWE-bench Pro (ScaleAI) ──────────────────────────────────────────────────
# Same sandbox machinery, but a different HF dataset + official Scale harness
# (per-instance run_script.sh + parser.py, vendored). Repo lives at /app.
def _load_swe_pro(**kw: Any):
    from ageneval.task.datasets.swe_bench_pro import load_swe_bench_pro_tasks
    kw = dict(kw)
    # A2E_SWE_PRO_INSTANCE pins a specific instance (e.g. one whose multi-GB
    # image is already pulled) for demos/tests; explicit instance_ids win.
    if not kw.get("instance_ids"):
        _pin = os.environ.get("A2E_SWE_PRO_INSTANCE")
        if _pin:
            kw["instance_ids"] = [_pin]
    return load_swe_bench_pro_tasks(
        "swe-bench-pro", **{k: v for k, v in kw.items() if k in ("n", "split", "instance_ids")}
    )


def _bind_swe_pro(**_kw: Any):
    from ageneval.task.datasets.swe_bench_pro import build_swe_bench_pro_binding
    return build_swe_bench_pro_binding()


def _score_swe_pro(task: Any, sandbox: Any, model_patch: str) -> Any:
    from ageneval.task.datasets.swe_bench_pro import score_swe_bench_pro
    return score_swe_bench_pro(task, sandbox, model_patch)


def _setup_swe_pro(task: Any, sandbox: Any) -> None:
    from ageneval.task.datasets.swe_bench_pro import setup_swe_bench_pro
    return setup_swe_bench_pro(task, sandbox)


# ─── Terminal-Bench 2.0 (laude-institute) ─────────────────────────────────────
# Same sandbox machinery as SWE-bench: each task's published docker image is the
# environment; the agent works via bash/editor tools, then the held-out verifier
# (tests/test.sh) is copied in and run to produce a 1/0 reward → ``resolved``.
def _load_tb2(**kw: Any):
    from ageneval.task.datasets.terminal_bench_2 import load_terminal_bench_2_tasks
    kw = dict(kw)
    # A2E_TB2_TASK pins one task (e.g. one whose image is already pulled) for
    # demos/tests; explicit task_ids win.
    if not kw.get("task_ids"):
        _pin = os.environ.get("A2E_TB2_TASK")
        if _pin:
            kw["task_ids"] = [_pin]
    return load_terminal_bench_2_tasks(**{k: v for k, v in kw.items() if k in ("n", "task_ids")})


def _bind_tb2(**_kw: Any):
    from ageneval.task.datasets.terminal_bench_2 import build_terminal_bench_2_binding
    return build_terminal_bench_2_binding()


def _score_tb2(task: Any, sandbox: Any, model_patch: str) -> Any:
    from ageneval.task.datasets.terminal_bench_2 import score_terminal_bench_2
    return score_terminal_bench_2(task, sandbox, model_patch)


def _setup_tb2(task: Any, sandbox: Any) -> None:
    from ageneval.task.datasets.terminal_bench_2 import setup_terminal_bench_2
    return setup_terminal_bench_2(task, sandbox)


# ─── Terminal-Bench 2.1 (harbor-framework) ───────────────────────────────────
def _load_tb21(**kw: Any):
    from ageneval.task.datasets.terminal_bench_2_1 import load_terminal_bench_2_1_tasks
    kw = dict(kw)
    if not kw.get("task_ids"):
        _pin = os.environ.get("AEP_TB21_TASK") or os.environ.get("A2E_TB21_TASK")
        if _pin:
            kw["task_ids"] = [_pin]
    return load_terminal_bench_2_1_tasks(
        **{k: v for k, v in kw.items() if k in ("n", "task_ids")}
    )


def _bind_tb21(**_kw: Any):
    from ageneval.task.datasets.terminal_bench_2_1 import build_terminal_bench_2_1_binding
    return build_terminal_bench_2_1_binding()


def _score_tb21(task: Any, sandbox: Any, model_patch: str) -> Any:
    from ageneval.task.datasets.terminal_bench_2_1 import score_terminal_bench_2_1
    return score_terminal_bench_2_1(task, sandbox, model_patch)


def _setup_tb21(task: Any, sandbox: Any) -> None:
    from ageneval.task.datasets.terminal_bench_2_1 import setup_terminal_bench_2_1
    return setup_terminal_bench_2_1(task, sandbox)


def _qa_load(bench: str) -> Callable:
    """Closure factory: load fn bound to one qa_suite benchmark key."""
    def _f(**kw: Any):
        from ageneval.task.datasets.qa_suite import load_qa_tasks
        return load_qa_tasks(bench, **{k: v for k, v in kw.items() if k in ("n", "split")})
    return _f


def _qa_bind(bench: str) -> Callable:
    """Closure factory: binding fn bound to one qa_suite benchmark key."""
    def _f(**_kw: Any):
        from ageneval.task.datasets.qa_suite import build_qa_binding
        return build_qa_binding(bench)
    return _f


# Default (recommended) evaluators per dataset. The UI pre-selects these when a
# dataset is chosen; the user can still add/remove any evaluator. Rationale:
#   - tool datasets   → trajectory correctness (tool_recall) + answer quality (llm_judge)
#   - multiple-choice → letter match (mc_letter) + llm_judge
#   - numeric (math)  → numeric_match + llm_judge
#   - free-form / code→ substring or exact_match + llm_judge
DATASETS: Dict[str, Dict[str, Any]] = {
    "tau-bench": {"load": _load_tau_bench, "bind": _bind_tau_bench, "kind": "tool",
                  "default_evaluators": ["tool_recall", "llm_judge"],
                  "agent_overrides": {"max_turns": 30, "max_steps": 30}},
    "tau2":      {"load": _load_tau2, "bind": _bind_tau2, "kind": "tool",
                  "default_evaluators": ["tool_recall", "llm_judge"],
                  "agent_overrides": {"max_turns": 30, "max_steps": 30}},
    "tau3":      {"load": _load_tau3, "bind": _bind_tau3, "kind": "tool",
                  "default_evaluators": ["tool_recall", "llm_judge"],
                  "agent_overrides": {"max_turns": 30, "max_steps": 30}},
    "tau3bench": {"load": _load_tau3, "bind": _bind_tau3, "kind": "tool",
                  "default_evaluators": ["tool_recall", "llm_judge"],
                  "agent_overrides": {"max_turns": 30, "max_steps": 30}},
    "tau3-bench": {"load": _load_tau3, "bind": _bind_tau3, "kind": "tool",
                   "default_evaluators": ["tool_recall", "llm_judge"],
                   "agent_overrides": {"max_turns": 30, "max_steps": 30}},
    "mmlu":      {"load": _load_mmlu, "bind": _bind_mmlu, "kind": "qa",
                  "default_evaluators": ["mc_letter", "llm_judge"],
                  "agent_overrides": {"max_turns": 8, "max_steps": 8}},
    "gsm8k":     {"load": _load_gsm8k, "bind": _bind_gsm8k, "kind": "qa",
                  "default_evaluators": ["numeric_match", "llm_judge"],
                  "agent_overrides": {"max_turns": 8, "max_steps": 8}},
    "humaneval": {"load": _load_humaneval, "bind": _bind_humaneval, "kind": "qa",
                  "default_evaluators": ["humaneval_pass"],
                  "agent_overrides": {"max_turns": 8, "max_steps": 8}},
    "persistbench": {"load": _load_persistbench, "bind": _bind_persistbench, "kind": "qa",
                     "default_evaluators": ["substring"],
                     "agent_overrides": {"max_turns": 8, "max_steps": 8}},
    "traject-bench": {"load": _load_traject_bench, "bind": _bind_traject_bench, "kind": "tool",
                      "default_evaluators": ["tool_recall", "llm_judge"],
                      "agent_overrides": {"max_turns": 8, "max_steps": 8}},
    "gdpval-aa": {"load": _load_gdpval, "bind": _bind_gdpval, "kind": "qa",
                  "default_evaluators": ["llm_judge"],
                  "agent_overrides": {"max_turns": 8, "max_steps": 8}},
    "deepsearchqa": {"load": _load_deepsearchqa, "bind": _bind_deepsearchqa, "kind": "tool",
                     "default_evaluators": ["deepsearch_match", "tool_recall"],
                     "agent_overrides": {"max_turns": 20, "max_steps": 20}},
}

# qa_suite — 10 config-driven pure-QA benchmarks (no sandbox/tools).
# Per-benchmark default evaluators keyed by answer style (mc / numeric / freeform).
_QA_DEFAULT_EVALS: Dict[str, list] = {
    "gpqa":          ["mc_letter", "llm_judge"],
    "mmlu-pro":      ["mc_letter", "llm_judge"],
    "arc-challenge": ["mc_letter", "llm_judge"],
    "truthfulqa":    ["mc_letter", "llm_judge"],
    "agieval":       ["mc_letter", "llm_judge"],
    "commonsenseqa": ["mc_letter", "llm_judge"],
    "hellaswag":     ["mc_letter", "llm_judge"],
    "openbookqa":    ["mc_letter", "llm_judge"],
    "bbh":           ["exact_match", "llm_judge"],
    "math":          ["numeric_match", "llm_judge"],
}
for _b in ("gpqa", "mmlu-pro", "arc-challenge", "truthfulqa", "bbh",
           "agieval", "commonsenseqa", "hellaswag", "openbookqa", "math"):
    DATASETS[_b] = {"load": _qa_load(_b), "bind": _qa_bind(_b), "kind": "qa",
                    "default_evaluators": _QA_DEFAULT_EVALS[_b],
                    "agent_overrides": {"max_turns": 8, "max_steps": 8}}

# Sandbox datasets — run inside a docker container; graded by score_swe_bench
# while the container is alive (see SandboxScoringRunner). ``agent_overrides``
# raise the agent's turn budget (a SWE fix needs many explore/edit steps).
for _v in ("swe-bench-lite", "swe-bench-verified"):
    DATASETS[_v] = {
        "load": _load_swe(_v), "bind": _bind_swe, "kind": "sandbox",
        "score": _score_swe, "setup": _setup_swe,
        "default_evaluators": ["swe_resolved", "swe_fail_to_pass", "swe_pass_to_pass"],
        "agent_overrides": {"max_turns": 40, "max_steps": 40},
    }

# SWE-bench Pro (ScaleAI) — official Scale harness grading (see swe_bench_pro pkg).
DATASETS["swe-bench-pro"] = {
    "load": _load_swe_pro, "bind": _bind_swe_pro, "kind": "sandbox",
    "score": _score_swe_pro, "setup": _setup_swe_pro,
    "default_evaluators": ["swe_resolved", "swe_fail_to_pass", "swe_pass_to_pass"],
    "agent_overrides": {"max_turns": 40, "max_steps": 40},
}

# Terminal-Bench 2.0 — sandbox dataset graded by the official held-out tests.
DATASETS["terminal-bench-2"] = {
    "load": _load_tb2, "bind": _bind_tb2, "kind": "sandbox",
    "score": _score_tb2, "setup": _setup_tb2,
    "default_evaluators": ["tb_resolved"],
    "agent_overrides": {"max_turns": 40, "max_steps": 40},
}

# Terminal-Bench 2.1 remains separate so published results preserve the version.
DATASETS["terminal-bench-2.1"] = {
    "load": _load_tb21, "bind": _bind_tb21, "kind": "sandbox",
    "score": _score_tb21, "setup": _setup_tb21,
    "default_evaluators": ["tb_resolved"],
    "agent_overrides": {"max_turns": 40, "max_steps": 40},
}


# ─── AGENTS ──────────────────────────────────────────────────────────────────


def _build_langgraph(*, binding: Any, **kw: Any):
    from ageneval.task.agents.langgraph import LangGraphAgent
    # Filter kwargs to what LangGraphAgent accepts. Sandbox datasets inject
    # agent_overrides with BOTH `max_turns` and `max_steps` (different agents
    # name their budget differently); LangGraphAgent uses `max_turns`, so drop
    # `max_steps` here — every sibling builder applies the same whitelist.
    accepted = {"model", "api_base", "api_key", "max_turns"}
    return LangGraphAgent(binding=binding, **{k: v for k, v in kw.items() if k in accepted})


def _build_claude_sdk(*, binding: Any, **kw: Any):
    """Build the generic ClaudeSDKAgent for any binding."""
    from ageneval.task.agents.claude_sdk import ClaudeSDKAgent
    # ClaudeSDKAgent talks Anthropic Messages API but can reuse the same
    # gateway credentials as OpenAI-compatible harnesses (api_base / api_key).
    accepted = {"model", "max_turns", "api_base", "api_key"}
    return ClaudeSDKAgent(binding=binding, **{k: v for k, v in kw.items() if k in accepted})


def _build_smolagents(*, binding: Any, **kw: Any):
    """Build the generic SmolAgentsAgent for any binding."""
    from ageneval.task.agents.smolagents import SmolAgentsAgent
    # Dataset overrides use max_turns; smolagents names the budget max_steps.
    if "max_steps" not in kw and kw.get("max_turns") is not None:
        kw = {**kw, "max_steps": kw["max_turns"]}
    accepted = {"model", "max_steps", "api_base", "api_key"}
    return SmolAgentsAgent(binding=binding, **{k: v for k, v in kw.items() if k in accepted})


def _build_openai_agents(*, binding: Any, **kw: Any):
    """Build the generic OpenAIAgentsAgent for any binding."""
    from ageneval.task.agents.openai_agents import OpenAIAgentsAgent
    accepted = {"model", "api_base", "api_key", "max_turns"}
    return OpenAIAgentsAgent(binding=binding, **{k: v for k, v in kw.items() if k in accepted})


def _build_google_adk(*, binding: Any, **kw: Any):
    """Build the generic GoogleADKAgent for any binding."""
    from ageneval.task.agents.google_adk import GoogleADKAgent
    accepted = {"model", "api_base", "api_key", "max_turns"}
    return GoogleADKAgent(binding=binding, **{k: v for k, v in kw.items() if k in accepted})


def _build_agno(*, binding: Any, **kw: Any):
    """Build the generic AgnoAgent for any binding."""
    from ageneval.task.agents.agno import AgnoAgent
    accepted = {"model", "api_base", "api_key", "max_turns"}
    return AgnoAgent(binding=binding, **{k: v for k, v in kw.items() if k in accepted})


def _build_llama_index(*, binding: Any, **kw: Any):
    """Build the generic LlamaIndexAgent for any binding."""
    from ageneval.task.agents.llama_index import LlamaIndexAgent
    accepted = {"model", "api_base", "api_key", "max_turns"}
    return LlamaIndexAgent(binding=binding, **{k: v for k, v in kw.items() if k in accepted})


def _build_crewai(*, binding: Any, **kw: Any):
    """Build the generic CrewAIAgent for any binding."""
    from ageneval.task.agents.crewai import CrewAIAgent
    accepted = {"model", "api_base", "api_key", "max_turns"}
    return CrewAIAgent(binding=binding, **{k: v for k, v in kw.items() if k in accepted})


def _build_autogen(*, binding: Any, **kw: Any):
    """Build the generic AutogenAgentChatAgent for any binding.

    autogen-agentchat lives in an ISOLATED uv project (``autogen-core`` pins
    protobuf<5.30, which conflicts with A2E). It is therefore not installed
    into the main workspace ``.venv``; importing it from there will fail with a
    clear instruction to use the isolated environment.
    """
    try:
        from ageneval.task.agents.autogen_agentchat import AutogenAgentChatAgent
    except ImportError as exc:
        raise RuntimeError(
            "autogen-agentchat is an isolated agent (protobuf conflict with "
            "A2E). Install and run it from its own environment:\n"
            "  cd task/agents/autogen_agentchat && "
            "uv sync --index-strategy unsafe-best-match"
        ) from exc
    accepted = {"model", "api_base", "api_key", "max_turns"}
    return AutogenAgentChatAgent(binding=binding, **{k: v for k, v in kw.items() if k in accepted})


AGENTS: Dict[str, Dict[str, Any]] = {
    "langgraph":     {"build": _build_langgraph,     "framework": "langchain",     "supports_any_binding": True},
    "claude-sdk":    {"build": _build_claude_sdk,    "framework": "anthropic",     "supports_any_binding": True},
    "smolagents":    {"build": _build_smolagents,    "framework": "smolagents",    "supports_any_binding": True},
    "openai-agents": {"build": _build_openai_agents, "framework": "openai_agents", "supports_any_binding": True},
    "google-adk":    {"build": _build_google_adk,    "framework": "google_adk",    "supports_any_binding": True},
    "agno":          {"build": _build_agno,          "framework": "agno",          "supports_any_binding": True},
    "llama-index":   {"build": _build_llama_index,   "framework": "llama_index",   "supports_any_binding": True},
    "crewai":        {"build": _build_crewai,        "framework": "crewai",        "supports_any_binding": True},
    "autogen-agentchat": {"build": _build_autogen,   "framework": "autogen_agentchat", "supports_any_binding": True, "isolated": True},
}


# Display grouping for the Run page <optgroup> taxonomy (UI-only metadata).
_AGENT_GROUP: Dict[str, str] = {
    "smolagents": "Agent-first frameworks",
    "agno": "Agent-first frameworks",
    "llama-index": "Agent-first frameworks",
    "langgraph": "Orchestration frameworks",
    "autogen-agentchat": "Orchestration frameworks",
    "crewai": "Orchestration frameworks",
    "google-adk": "Orchestration frameworks",
    "claude-sdk": "Vendor agent SDKs",
    "openai-agents": "Vendor agent SDKs",
}


def framework_for_agent(agent: str) -> Framework:
    """Single source of truth: which OpenInference instrumentor an agent needs."""
    return AGENTS.get(agent, {}).get("framework", "none")


def build_experiment_metadata(*, agent_name: str, agent: Any, sdk: str) -> Dict[str, Any]:
    """Metadata stored on A2E experiments for downstream DB analysis."""
    return {
        "agent_framework": agent_name,
        "model": getattr(agent, "model", None) or getattr(agent, "_model_name", None),
        "sdk": sdk,
    }


# ─── EVALUATORS ──────────────────────────────────────────────────────────────


def _final_answer(output: dict) -> str:
    """Return the agent's answer, unwrapping a ``{"final_answer": ...}`` JSON
    envelope if present.

    Many dataset bindings prescribe a JSON-action protocol, so an agent's
    ``final_answer`` field is frequently the *string* ``{"final_answer": "B"}``
    rather than the bare answer. Comparing that envelope verbatim would make
    exact/substring matching spuriously fail, so unwrap it first.
    """
    raw = (output or {}).get("final_answer", "")
    if not raw:
        return ""
    s = str(raw).strip()
    if s.startswith("{") and "final_answer" in s:
        try:
            obj = json.loads(s)
        except (ValueError, TypeError):
            return s
        if isinstance(obj, dict) and "final_answer" in obj:
            return str(obj["final_answer"]).strip()
    return s


def _eval_exact_match(output: dict, expected: dict) -> float:
    answer = _final_answer(output)
    ref = ((expected or {}).get("expected_outputs") or [""])[0]
    return float(str(answer).strip().lower() == str(ref).strip().lower())


def _eval_substring(output: dict, expected: dict) -> float:
    answer = _final_answer(output)
    golds = list((expected or {}).get("expected_outputs") or [])
    if not answer or not golds:
        return 0.0
    hits = sum(1 for s in golds if str(s).lower() in str(answer).lower())
    return hits / len(golds)


def _eval_tool_recall(output: dict, expected: dict) -> float:
    called = set((output or {}).get("tool_calls", []))
    expected_names = {a.get("name") for a in (expected or {}).get("expected_actions", []) if a.get("name")}
    if not expected_names:
        return 0.0
    return len(called & expected_names) / len(expected_names)


_NUM_RE = re.compile(r"-?\d+(?:\.\d+)?")
_FRAC_RE = re.compile(r"\\d?frac\s*\{\s*(-?\d+)\s*\}\s*\{\s*(-?\d+)\s*\}")
_SLASH_RE = re.compile(r"(-?\d+)\s*/\s*(-?\d+)")


def _parse_math_number(text: str) -> float | None:
    """Parse a MATH-style answer: LaTeX fraction, a/b, or a plain number."""
    s = str(text or "").strip()
    if not s:
        return None
    s = s.replace(",", "").replace("$", "").strip()
    fracs = list(_FRAC_RE.finditer(s))
    if fracs:
        m = fracs[-1]
        den = float(m.group(2))
        return None if den == 0 else float(m.group(1)) / den
    tail = s.split()[-1] if s.split() else s
    m = _SLASH_RE.fullmatch(s) or _SLASH_RE.fullmatch(tail)
    if m:
        den = float(m.group(2))
        return None if den == 0 else float(m.group(1)) / den
    nums = _NUM_RE.findall(s)
    if not nums:
        return None
    try:
        return float(nums[-1])
    except (ValueError, TypeError):
        return None


def _eval_numeric_match(output: dict, expected: dict) -> float:
    """Compare the agent's numeric answer against expected[0].

    Unwraps a ``{"final_answer": ...}`` envelope and accepts fractions /
    LaTeX ``\\frac{a}{b}`` so MATH items are not scored by a digits-only regex.
    """
    answer = _final_answer(output)
    pred = _parse_math_number(answer)
    ref = _parse_math_number(((expected or {}).get("expected_outputs") or [""])[0])
    if pred is None or ref is None:
        return 0.0
    return float(abs(pred - ref) < 1e-6)


_SET_SPLIT_RE = re.compile(r"\s*(?:,|;|\band\b|\n)\s*", re.IGNORECASE)


def _deepsearch_items(text: str) -> list[str]:
    parts = [re.sub(r"\s+", " ", p).strip(" .;:") for p in _SET_SPLIT_RE.split(text or "")]
    return [p.lower() for p in parts if p]


def _eval_deepsearch_match(output: dict, expected: dict, input: dict) -> float:
    """DeepSearchQA outcome metric: single-answer containment or set-item recall.

    Official autorater is gemini-2.5-flash. This deterministic stand-in scores
    Single Answer as 1 iff the gold string appears in the reply, and Set Answer
    as the fraction of gold items found in the reply.
    """
    answer = _final_answer(output)
    gold = str(((expected or {}).get("expected_outputs") or [""])[0] or "")
    if not answer or not gold:
        return 0.0
    state = (input or {}).get("initial_state") or {}
    answer_type = str(state.get("answer_type") or "Single Answer")
    if answer_type != "Set Answer":
        g = gold.strip().lower()
        a = answer.strip().lower()
        return float(g == a or g in a)
    golds = _deepsearch_items(gold)
    if not golds:
        return 0.0
    blob = answer.lower()
    pred = set(_deepsearch_items(answer))
    hits = sum(1 for g in golds if g in pred or g in blob)
    return hits / len(golds)


def _eval_humaneval_pass(output: dict, expected: dict, input: dict) -> float:
    """Official HumanEval pass@1: run hidden unit tests, not substring-of-canonical."""
    from ageneval.task.datasets.humaneval import score_humaneval_state

    state = (input or {}).get("initial_state") or {}
    # Do not use ``_final_answer``: its ``.strip()`` drops the leading indent
    # that a function body needs when concatenated onto the official prompt.
    raw = str((output or {}).get("final_answer", "") or "")
    if raw.lstrip().startswith("{") and "final_answer" in raw:
        try:
            obj = json.loads(raw)
        except (ValueError, TypeError):
            obj = None
        if isinstance(obj, dict) and "final_answer" in obj:
            raw = str(obj["final_answer"])
    result = score_humaneval_state(raw, state)
    return 1.0 if result.get("passed") else 0.0


def _eval_mc_letter(output: dict, expected: dict) -> float:
    """For multiple-choice benchmarks: extract the answer letter.

    Range is A-J (not just A-D) because MMLU-Pro has up to 10 options and
    CommonsenseQA has 5; restricting to A-D would silently score any E-J
    answer as wrong. The answer is first unwrapped from a JSON envelope.
    """
    answer = _final_answer(output) or str((output or {}).get("final_answer", ""))
    m = re.search(r"\b([A-J])\b", answer.upper())
    if not m:
        return 0.0
    ref = str(((expected or {}).get("expected_outputs") or [""])[0]).strip().upper()
    return float(m.group(1) == ref)


def _eval_swe_resolved(output: dict) -> float:
    """Sandbox (SWE-bench) metric: surface the ``resolved`` boolean produced by
    ``SandboxScoringRunner`` (which graded the patch while the container was
    still alive). A2E evaluators run *after* the task fn returns — by then
    the container is gone — so the heavy grading already happened upstream and
    this evaluator only reads the result.
    """
    return 1.0 if (output or {}).get("resolved") else 0.0


_eval_swe_resolved.__name__ = _eval_swe_resolved.__qualname__ = "swe_resolved"


def _eval_swe_fail_to_pass(output: dict) -> float:
    """SWE-bench partial-credit metric: fraction of the instance's FAIL_TO_PASS
    tests (the bug's target tests) that the model's patch flipped fail->pass.
    1.0 means every target test now passes (necessary for ``resolved``); 0.0
    means the fix addressed none. Reads counts produced upstream by the grader.
    """
    o = output or {}
    total = o.get("swe_f2p_total") or 0
    return (o.get("swe_f2p_passed") or 0) / total if total else 0.0


def _eval_swe_pass_to_pass(output: dict) -> float:
    """SWE-bench regression metric: fraction of PASS_TO_PASS tests that still
    pass after the model's patch. 1.0 means the patch introduced no regression;
    < 1.0 means it broke previously-passing tests. Reads grader counts.
    """
    o = output or {}
    total = o.get("swe_p2p_total") or 0
    return (o.get("swe_p2p_passed") or 0) / total if total else 0.0


_eval_swe_fail_to_pass.__name__ = _eval_swe_fail_to_pass.__qualname__ = "swe_fail_to_pass"
_eval_swe_pass_to_pass.__name__ = _eval_swe_pass_to_pass.__qualname__ = "swe_pass_to_pass"


def _eval_tb_resolved(output: dict) -> float:
    """Terminal-Bench 2 metric: 1.0 iff the held-out verifier reward was 1.

    ``score_terminal_bench_2`` runs ``tests/test.sh`` while the container is alive
    and surfaces the reward as ``resolved`` on ``TaskTrace.raw`` (A2E
    evaluators run after the container is gone, so this only reads the result).
    """
    return 1.0 if (output or {}).get("resolved") else 0.0


_eval_tb_resolved.__name__ = _eval_tb_resolved.__qualname__ = "tb_resolved"


def make_llm_judge(llm: Any, *, label: str = "llm_judge") -> Callable[[dict, dict, dict], Any]:
    """Prompted-text LLM-as-judge (works with reasoner-style models that lack tool_choice)."""
    prompt_tmpl = (
        "You are an evaluator. Decide whether the agent's answer satisfies the user's request.\n"
        "Return EXACTLY one line: SCORE=<0 or 1>; EXPLANATION=<one sentence>\n\n"
        "User instruction: {instruction}\n"
        "Agent answer: {answer}\n"
        "Expected answer hint: {expected}\n"
    )

    def fn(output: dict, expected: dict, input: dict) -> Any:
        prompt = prompt_tmpl.format(
            instruction=input.get("instruction", ""),
            answer=(output or {}).get("final_answer", "") or "(no answer)",
            expected=((expected or {}).get("expected_outputs") or [""])[0],
        )
        try:
            text = llm.generate_text(prompt=prompt)
        except Exception as exc:  # noqa: BLE001
            return {"score": 0.0, "label": "error", "explanation": str(exc)[:200]}
        m_score = re.search(r"SCORE\s*=\s*([01](?:\.\d+)?)", text or "")
        m_expl = re.search(r"EXPLANATION\s*=\s*(.+?)(?:\n|$)", text or "")
        score = float(m_score.group(1)) if m_score else 0.0
        return {
            "score": score,
            "label": "correct" if score >= 0.5 else "incorrect",
            "explanation": (m_expl.group(1) if m_expl else (text or ""))[:500],
        }

    # A2E derives the annotation name from __qualname__; set both so the
    # experiment UI shows a clean evaluator name instead of "fn".
    fn.__name__ = label
    fn.__qualname__ = label
    return fn


# Clean evaluator names for the A2E experiment UI. A2E reads
# __qualname__ (not __name__), so set both to the registry key.
for _eval_fn, _eval_name in (
    (_eval_exact_match, "exact_match"),
    (_eval_substring, "substring"),
    (_eval_tool_recall, "tool_recall"),
    (_eval_numeric_match, "numeric_match"),
    (_eval_mc_letter, "mc_letter"),
    (_eval_humaneval_pass, "humaneval_pass"),
    (_eval_deepsearch_match, "deepsearch_match"),
):
    _eval_fn.__name__ = _eval_name
    _eval_fn.__qualname__ = _eval_name


EVALUATORS: Dict[str, Callable[..., Any]] = {
    "exact_match": _eval_exact_match,
    "substring": _eval_substring,
    "tool_recall": _eval_tool_recall,
    "numeric_match": _eval_numeric_match,
    "mc_letter": _eval_mc_letter,
    "humaneval_pass": _eval_humaneval_pass,
    "deepsearch_match": _eval_deepsearch_match,
    "swe_resolved": _eval_swe_resolved,
    "swe_fail_to_pass": _eval_swe_fail_to_pass,
    "swe_pass_to_pass": _eval_swe_pass_to_pass,
    "tb_resolved": _eval_tb_resolved,
    # "llm_judge" is special: built dynamically when an LLM is provided.
}


def list_registries() -> Dict[str, Any]:
    """Return discoverable names + metadata (used by CLI --list and UI dropdowns).

    The string lists ``datasets`` / ``agents`` / ``evaluators`` are kept as-is for
    backward compatibility. ``agent_meta`` / ``dataset_meta`` are added so the UI
    can render grouped dropdowns and capability hints without hard-coding them.
    """
    return {
        "datasets": sorted(DATASETS),
        "agents": sorted(AGENTS),
        "evaluators": sorted(EVALUATORS) + ["llm_judge"],
        "agent_meta": {
            name: {
                "framework": meta.get("framework", "none"),
                "group": _AGENT_GROUP.get(name, "Agent-first frameworks"),
                "isolated": bool(meta.get("isolated", False)),
            }
            for name, meta in AGENTS.items()
        },
        "dataset_meta": {
            name: {
                "kind": meta.get("kind", "qa"),
                "default_evaluators": list(meta.get("default_evaluators", [])),
            }
            for name, meta in DATASETS.items()
        },
    }
