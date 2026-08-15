from __future__ import annotations

import asyncio
from contextlib import contextmanager
from types import SimpleNamespace

import ageneval.task.sandbox as sandbox_module
from ageneval.task.core import SandboxScoringRunner, TaskInput, TaskTrace
from ageneval.task.sandbox import SandboxSpec


def test_full_harness_hooks_prepare_and_run_inside_sandbox(monkeypatch) -> None:
    events: list[object] = []

    class Harness:
        name = "harness"

        async def prepare_sandbox(self, task, spec):
            events.append(("prepare", task.task_id, spec.config["image"]))
            return SandboxSpec(type="docker", config={**spec.config, "image": "derived"})

        async def run_in_sandbox(self, task, sandbox):
            events.append(("run", task.initial_state["__sandbox__"] is sandbox))
            return TaskTrace(
                task_id=task.task_id,
                agent_name=self.name,
                status="ok",
                turns=2,
            )

        async def run(self, _task):
            raise AssertionError("legacy host run must not be used")

    fake_sandbox = SimpleNamespace(
        exec=lambda _command: SimpleNamespace(stdout="patch"),
    )

    @contextmanager
    def fake_session(spec):
        events.append(("session", spec.config["image"]))
        yield fake_sandbox

    monkeypatch.setattr(sandbox_module, "sandbox_session", fake_session)
    runner = SandboxScoringRunner(
        inner=Harness(),
        score_fn=lambda _task, sandbox, patch: {
            "resolved": sandbox is fake_sandbox and patch == "patch"
        },
    )
    trace = asyncio.run(
        runner.run(
            TaskInput(
                task_id="one",
                instruction="fix it",
                sandbox={"type": "docker", "config": {"image": "base"}},
            )
        )
    )

    assert events == [
        ("prepare", "one", "base"),
        ("session", "derived"),
        ("run", True),
    ]
    assert trace.status == "ok"
    assert trace.raw == {"model_patch": "patch", "resolved": True}


def test_legacy_agent_still_runs_through_injected_sandbox(monkeypatch) -> None:
    class LegacyAgent:
        name = "legacy"

        async def run(self, task):
            assert task.initial_state["__sandbox__"] is fake_sandbox
            return TaskTrace(
                task_id=task.task_id,
                agent_name=self.name,
                status="ok",
                turns=1,
            )

    fake_sandbox = SimpleNamespace(
        exec=lambda _command: SimpleNamespace(stdout=""),
    )

    @contextmanager
    def fake_session(_spec):
        yield fake_sandbox

    monkeypatch.setattr(sandbox_module, "sandbox_session", fake_session)
    runner = SandboxScoringRunner(
        inner=LegacyAgent(),
        score_fn=lambda *_args: {"resolved": True},
    )
    trace = asyncio.run(
        runner.run(
            TaskInput(
                task_id="legacy",
                instruction="fix it",
                sandbox={"type": "docker", "config": {"image": "base"}},
            )
        )
    )

    assert trace.status == "ok"
    assert trace.raw["resolved"] is True
