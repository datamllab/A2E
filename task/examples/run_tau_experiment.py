"""End-to-end τ-bench experiment visible in A2E UI.

What this script does
---------------------
1. Sets up OpenInference instrumentation (langchain).
2. Uploads τ-bench tasks to A2E as a *Dataset* (visible in UI under
   "Datasets").
3. Wraps the multi-agent `LangGraphTauAgent` as a A2E *experiment task*.
4. Attaches two A2E evaluators:
     - `exact_match` (code-based)
     - `ToolSelectionEvaluator` (LLM-as-judge)
5. Calls `run_experiment` → the entire flow (input → agent output →
   evaluator scores) lands in A2E under "Experiments" with full trace
   linkage.

Usage
-----
    # 1. start a2e in another shell
    uv run a2e serve

    # 2. then:
    OPENAI_API_KEY=...  OPENAI_API_BASE=http://.../v1/  \
      A2E_LANGGRAPH_MODEL=deepseek-v4-pro \
      uv run --frozen python examples/run_tau_experiment.py --domain retail

Open http://localhost:6006 → Datasets / Experiments tab.
"""

from __future__ import annotations

import argparse
import asyncio
import json
import logging
import os
import sys
from typing import Any

from ageneval.task.agents.langgraph import LangGraphTauAgent
from ageneval.task.core import setup_instrumentation
from ageneval.task.datasets.tau_bench import load_tau_bench_tasks
from ageneval.task.runners import (
    DEFAULT_SAMPLE_SIZE,
    build_experiment_metadata,
    build_run_identity,
    sample_dataset,
)

logger = logging.getLogger(__name__)


def _build_examples(tasks):
    """Convert TaskInput records into a2e-client dataset rows."""
    rows = []
    for t in tasks:
        rows.append(
            {
                "input": {"instruction": t.instruction, "initial_state": dict(t.initial_state)},
                "output": {
                    "expected_outputs": list(t.expected_outputs),
                    "expected_actions": list(t.expected_actions),
                },
                "metadata": {"task_id": t.task_id, **dict(t.metadata)},
            }
        )
    return rows


def _make_task_fn(agent: LangGraphTauAgent):
    """Build a a2e-experiment-compatible task function backed by ``agent``."""
    from ageneval.task.core import TaskInput

    def task_fn(input: dict, metadata: dict) -> dict:
        task_input = TaskInput(
            task_id=metadata.get("task_id", "?"),
            instruction=input.get("instruction", ""),
            initial_state=input.get("initial_state", {}),
        )
        trace = asyncio.run(agent.run(task_input))
        return {
            "final_answer": trace.final_answer or "",
            "tool_calls": [tc.name for tc in trace.tool_calls],
            "status": trace.status,
            "turns": trace.turns,
            "trace_id": trace.trace_id,
            "error": trace.error,
        }

    return task_fn


def _build_evaluators(*, llm: Any | None):
    """Mix of code-based + LLM-as-judge evaluators (a2e-evals)."""

    evaluators: list = []

    # 1. Code-based: every expected output must appear in the final answer.
    def expected_substring_match(output: dict, expected: dict) -> float:
        answer = (output or {}).get("final_answer", "")
        if not answer:
            return 0.0
        hits = sum(1 for s in (expected or {}).get("expected_outputs", []) if str(s).lower() in answer.lower())
        denom = max(1, len((expected or {}).get("expected_outputs", [])))
        return hits / denom

    expected_substring_match.__name__ = "expected_substring_match"
    evaluators.append(expected_substring_match)

    # 2. Code-based: expected tool names appear in the call list.
    def tool_call_recall(output: dict, expected: dict) -> float:
        called = set((output or {}).get("tool_calls", []))
        expected_names = {a.get("name") for a in (expected or {}).get("expected_actions", []) if a.get("name")}
        if not expected_names:
            return 1.0
        return len(called & expected_names) / len(expected_names)

    tool_call_recall.__name__ = "tool_call_recall"
    evaluators.append(tool_call_recall)

    # 3. Code-based: exact_match on final answer == first expected output.
    def exact_first_expected(output: dict, expected: dict) -> float:
        answer = (output or {}).get("final_answer", "")
        ref = ((expected or {}).get("expected_outputs") or [""])[0]
        return float(answer.strip().lower() == str(ref).strip().lower())

    exact_first_expected.__name__ = "exact_first_expected"
    evaluators.append(exact_first_expected)

    # 4. LLM-as-judge (prompted-text fallback that works with reasoner models
    # which do not support tool_choice / structured_output).
    if llm is not None:
        import re

        prompt_tmpl = (
            "You are an evaluator. Decide whether the agent's answer satisfies the user's request.\n"
            "Return EXACTLY one line: SCORE=<0 or 1>; EXPLANATION=<one sentence>\n\n"
            "User instruction: {instruction}\n"
            "Agent answer: {answer}\n"
            "Expected answer hint: {expected}\n"
        )

        def llm_correctness(output: dict, expected: dict, input: dict) -> Any:
            prompt = prompt_tmpl.format(
                instruction=input.get("instruction", ""),
                answer=(output or {}).get("final_answer", "") or "(no answer)",
                expected=((expected or {}).get("expected_outputs") or [""])[0],
            )
            try:
                text = llm.generate_text(prompt=prompt)  # type: ignore[attr-defined]
            except Exception as exc:
                return {"score": 0.0, "label": "error", "explanation": str(exc)[:200]}
            m_score = re.search(r"SCORE\s*=\s*([01](?:\.\d+)?)", text or "")
            m_expl = re.search(r"EXPLANATION\s*=\s*(.+?)(?:\n|$)", text or "")
            score = float(m_score.group(1)) if m_score else 0.0
            return {
                "score": score,
                "label": "correct" if score >= 0.5 else "incorrect",
                "explanation": (m_expl.group(1) if m_expl else (text or ""))[:500],
            }

        llm_correctness.__name__ = "llm_correctness"
        evaluators.append(llm_correctness)

    return evaluators


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--domain", default="retail", choices=["retail", "airline"])
    parser.add_argument("--n", type=int, default=DEFAULT_SAMPLE_SIZE)
    parser.add_argument("--sample-seed", type=int, default=None)
    parser.add_argument("--run-id", default=None)
    parser.add_argument("--experiment-name", default=None)
    parser.add_argument("--endpoint", default=None, help="OTLP endpoint override")
    parser.add_argument("--model", default=None, help="overrides A2E_LANGGRAPH_MODEL")
    parser.add_argument("--api-base", default=None, help="overrides OPENAI_API_BASE")
    parser.add_argument("--api-key", default=None, help="overrides OPENAI_API_KEY")
    parser.add_argument("--no-llm-judge", action="store_true", help="skip LLM-as-judge evaluator")
    args = parser.parse_args()

    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(name)s [%(levelname)s] %(message)s")
    if args.n <= 0:
        parser.error("--n must be a positive integer")

    # 1. Load the complete domain and draw this run's exact random sample.
    tasks = load_tau_bench_tasks(domain=args.domain, n=None)
    tasks, selection = sample_dataset(
        tasks,
        n=args.n,
        seed=args.sample_seed,
    )
    examples = _build_examples(tasks.tasks)

    # 2. Build a unique identity before instrumentation or persistence.
    agent = LangGraphTauAgent(
        domain=args.domain,
        model=args.model,
        api_base=args.api_base,
        api_key=args.api_key,
    )
    actual_model = str(getattr(agent, "_model_name", None) or args.model or "default-model")
    identity = build_run_identity(
        dataset_name=tasks.name,
        dataset_key=f"tau-bench-{args.domain}",
        agent_name="langgraph",
        model=actual_model,
        run_id=args.run_id,
    )

    # 3. Instrumentation (so the agent's spans land in a2e).
    provider = setup_instrumentation(
        project_name=args.experiment_name or identity.project_name,
        endpoint=args.endpoint,
        framework="langchain",
    )

    # 4. Upload as a new A2E dataset. Persistence errors must propagate; they
    # must never be converted into reuse of an older dataset version.
    from a2e.client import Client  # type: ignore

    client = Client()
    dataset_name = identity.dataset_name
    dataset = client.datasets.create_dataset(
        name=dataset_name,
        examples=examples,
        dataset_description=(
            f"tau-bench {args.domain} run {identity.run_id} "
            f"({len(examples)} of {selection.available_n} examples)"
        ),
    )
    print(f"✓ uploaded isolated dataset '{dataset_name}' with {len(examples)} examples")
    print(f"  sampling: random; seed={selection.seed}; task_ids={list(selection.task_ids)}")

    # 5. Build the A2E experiment task.
    task_fn = _make_task_fn(agent)

    # 6. Build evaluators (code + optional LLM-as-judge).
    judge_llm = None
    if not args.no_llm_judge:
        try:
            from a2e.evals.llm import LLM  # type: ignore

            judge_kwargs: dict[str, Any] = {
                "provider": "openai",
                "model": args.model or os.environ.get("A2E_LANGGRAPH_MODEL") or "gpt-4o-mini",
            }
            if args.api_base or os.environ.get("OPENAI_API_BASE"):
                judge_kwargs["base_url"] = args.api_base or os.environ["OPENAI_API_BASE"]
            if args.api_key or os.environ.get("OPENAI_API_KEY"):
                judge_kwargs["api_key"] = args.api_key or os.environ["OPENAI_API_KEY"]
            judge_llm = LLM(**judge_kwargs)
        except Exception as exc:
            logger.warning("LLM judge construction failed: %s — skipping", exc)
    evaluators = _build_evaluators(llm=judge_llm)

    # 7. Run the experiment.
    from a2e.client.experiments import run_experiment  # type: ignore

    print(f"▶ running experiment over {len(examples)} examples …")
    ran = run_experiment(
        dataset=dataset,
        task=task_fn,
        evaluators=evaluators,
        experiment_name=args.experiment_name or identity.experiment_name,
        experiment_description=(
            f"tau-bench {args.domain} run {identity.run_id} via langgraph"
        ),
        experiment_metadata={
            **build_experiment_metadata(
                agent_name="langgraph",
                agent=agent,
                sdk="langchain",
            ),
            "run_id": identity.run_id,
            "dataset": "tau-bench",
            "sampling_strategy": selection.strategy,
            "sample_seed": selection.seed,
            "requested_n": selection.requested_n,
            "available_n": selection.available_n,
            "selected_n": selection.selected_n,
            "sample_task_ids": list(selection.task_ids),
        },
    )

    print()
    print("✓ experiment finished")
    print(f"  run_id: {identity.run_id}")
    print("  open http://localhost:6006/datasets to see the τ-bench dataset")
    print("  open http://localhost:6006/experiments to see this run's per-example scores")
    if hasattr(ran, "summary"):
        try:
            print(json.dumps(ran.summary, ensure_ascii=False, indent=2, default=str)[:1500])
        except Exception:
            pass

    provider.force_flush(timeout_millis=8000)
    return 0


if __name__ == "__main__":
    sys.exit(main())
