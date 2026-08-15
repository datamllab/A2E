"""Run and score an AgentRunner against a per-task sandbox.

Flow for one sandbox task:

    1. resolve the sandbox spec from ``TaskInput.sandbox``;
    2. let a coding harness optionally prepare a derived task image;
    3. start the environment and run optional dataset setup;
    4. run a harness-provided ``run_in_sandbox`` implementation when present;
       otherwise run the legacy host agent with the live sandbox injected into
       ``initial_state["__sandbox__"]`` for dataset binding tools;
    5. extract the model diff and invoke the official scorer while the edited
       sandbox is still alive.

The optional hooks keep complete coding harnesses and their native tools inside
Docker benchmark containers without changing existing SDK-agent behaviour.
"""

from __future__ import annotations

import inspect
import logging
import time
from collections.abc import Callable, Mapping, Sequence
from dataclasses import dataclass, field, replace
from typing import TYPE_CHECKING, Any

from ageneval.task.core.agent import AgentRunner
from ageneval.task.core.dataset import TaskInput
from ageneval.task.core.result import TaskTrace

if TYPE_CHECKING:
    from ageneval.task.sandbox import SandboxEnvironment

logger = logging.getLogger(__name__)

# (task, sandbox) -> None; (task, sandbox, model_patch) -> report dict
SetupFn = Callable[[TaskInput, "SandboxEnvironment"], None]
ScoreFn = Callable[[TaskInput, "SandboxEnvironment", str], Mapping[str, Any]]


@dataclass
class SandboxScoringRunner(AgentRunner):
    """Run an inner agent inside a per-task sandbox and score the result."""

    inner: AgentRunner
    score_fn: ScoreFn
    setup_fn: SetupFn | None = None
    patch_cmd: Sequence[str] = ("git", "diff")
    name: str = field(init=False)

    def __post_init__(self) -> None:
        self.name = f"sandbox::{getattr(self.inner, 'name', 'agent')}"

    async def run(self, task: TaskInput) -> TaskTrace:
        from ageneval.task.sandbox import SandboxSpec, sandbox_session

        start = time.perf_counter()
        spec = SandboxSpec.from_obj(task.sandbox)
        if spec is None:
            return TaskTrace(
                task_id=task.task_id,
                agent_name=self.name,
                status="error",
                turns=0,
                elapsed_seconds=time.perf_counter() - start,
                error="sandbox dataset task is missing a 'sandbox' spec",
            )

        try:
            # Full coding harnesses may augment the task image with their
            # runtime before it starts. Existing SDK agents do not implement
            # this optional hook and retain the binding-tool path below.
            prepare_sandbox = getattr(self.inner, "prepare_sandbox", None)
            if callable(prepare_sandbox):
                prepared = prepare_sandbox(task, spec)
                spec = await prepared if inspect.isawaitable(prepared) else prepared
            with sandbox_session(spec) as sb:
                if self.setup_fn is not None:
                    self.setup_fn(task, sb)
                inner_task = replace(
                    task,
                    initial_state={**dict(task.initial_state), "__sandbox__": sb},
                )
                run_in_sandbox = getattr(self.inner, "run_in_sandbox", None)
                if callable(run_in_sandbox):
                    trace = await run_in_sandbox(inner_task, sb)
                else:
                    trace = await self.inner.run(inner_task)
                model_patch = sb.exec(list(self.patch_cmd)).stdout
                try:
                    report = dict(self.score_fn(task, sb, model_patch))
                except Exception as exc:
                    logger.exception("scorer failed on %s", task.task_id)
                    report = {"resolved": False, "score_error": str(exc)[:500]}
        except Exception as exc:
            logger.exception("sandbox failed on %s", task.task_id)
            return TaskTrace(
                task_id=task.task_id,
                agent_name=self.name,
                status="error",
                turns=0,
                elapsed_seconds=time.perf_counter() - start,
                error=f"sandbox error: {exc}"[:1000],
            )

        raw = {**dict(trace.raw), "model_patch": model_patch, **report}
        return replace(
            trace,
            agent_name=self.name,
            raw=raw,
            elapsed_seconds=trace.elapsed_seconds or (time.perf_counter() - start),
        )
