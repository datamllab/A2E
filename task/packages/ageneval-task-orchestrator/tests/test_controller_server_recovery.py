from __future__ import annotations

import asyncio
from types import SimpleNamespace

from ageneval.task.orchestrator.controller import CampaignController


def test_stale_server_ids_are_discarded_before_resume() -> None:
    updates: list[dict] = []
    controller = CampaignController.__new__(CampaignController)
    controller.plan = SimpleNamespace(
        campaign_id="campaign-1",
        cells=[SimpleNamespace(cell_id="cell-1", benchmark="benchmark-1")],
    )
    controller.tasks = {"benchmark-1": [{"task_id": "task-1"}]}
    controller.lock = {}
    controller.run_directory = SimpleNamespace(update_lock=updates.append)

    class Sink:
        async def locked_dataset_exists(self, **_kwargs) -> bool:
            return False

        async def locked_experiment_exists(self, **_kwargs) -> bool:
            raise AssertionError("experiment validation must stop after a stale dataset")

    state = {
        "datasets": {
            "benchmark-1": {
                "id": "dataset-old",
                "version_id": "version-old",
                "examples": {"task-1": "example-old"},
            }
        },
        "cells": {
            "cell-1": {
                "experiment_id": "experiment-old",
                "project_name": "project-old",
            }
        },
    }

    recovered = asyncio.run(controller._validated_server_state(Sink(), state))

    assert recovered == {"datasets": {}, "cells": {}}
    assert controller.lock["server"] == recovered
    assert updates == [{"server": recovered}]


def test_campaign_experiments_emit_standard_identity_metadata() -> None:
    updates: list[dict] = []
    captured: dict = {}
    controller = CampaignController.__new__(CampaignController)
    controller.plan = SimpleNamespace(
        campaign_id="campaign-1",
        cells=[
            SimpleNamespace(
                cell_id="cell-1",
                benchmark="benchmark-1",
                harness="langgraph",
                model="profile-1",
                profile_digest="profile-digest",
            )
        ],
    )
    controller.config = SimpleNamespace(name="campaign", repetitions=1)
    controller.tasks = {
        "benchmark-1": [
            {"task_id": "task-1", "instruction": "do the task", "metadata": {}}
        ]
    }
    controller.benchmarks = {
        "benchmark-1": {
            "profile_digest": "benchmark-digest",
            "selection": {"task_ids": ["task-1"]},
        }
    }
    controller.profiles = {"profile-1": SimpleNamespace(model="gpt-5.6-sol")}
    controller.lock = {}
    controller.run_directory = SimpleNamespace(update_lock=updates.append)

    class Sink:
        async def ensure_dataset(self, **_kwargs):
            return (
                SimpleNamespace(
                    id="dataset-1",
                    version_id="version-1",
                    name="dataset-name",
                ),
                {"task-1": "example-1"},
            )

        async def ensure_experiment(self, **kwargs):
            captured.update(kwargs)
            return {"id": "experiment-1", "project_name": "project-1"}

    asyncio.run(controller._ensure_server_objects(Sink()))

    assert captured["metadata"] == {
        "campaign_id": "campaign-1",
        "cell_id": "cell-1",
        "agent_framework": "langgraph",
        "sdk": "langchain",
        "model": "gpt-5.6-sol",
        "model_profile": "profile-1",
        "model_profile_digest": "profile-digest",
        "benchmark": "benchmark-1",
        "benchmark_profile_digest": "benchmark-digest",
        "harness": "langgraph",
        "sample": {"task_ids": ["task-1"]},
    }
