from __future__ import annotations

import asyncio
from datetime import datetime, timezone
from types import SimpleNamespace

import httpx
from ageneval.task.orchestrator.schema import GradeResult, TrialResult
from ageneval.task.orchestrator.sink import A2ESink


def _sink(handler) -> A2ESink:
    from a2e.client import AsyncClient

    sink = A2ESink.__new__(A2ESink)
    sink.client = AsyncClient(
        http_client=httpx.AsyncClient(
            base_url="http://a2e.test/", transport=httpx.MockTransport(handler)
        )
    )
    return sink


def test_locked_dataset_mapping_must_match_current_server() -> None:
    class Datasets:
        async def get_dataset(self, **_kwargs):
            return SimpleNamespace(
                id="dataset-1",
                version_id="version-1",
                examples=[{"id": "example-1", "metadata": {"task_id": "task-1"}}],
            )

    async def scenario() -> None:
        sink = A2ESink.__new__(A2ESink)
        sink.client = SimpleNamespace(datasets=Datasets())
        assert await sink.locked_dataset_exists(
            dataset_id="dataset-1",
            version_id="version-1",
            expected_examples={"task-1": "example-1"},
        )
        assert not await sink.locked_dataset_exists(
            dataset_id="dataset-1",
            version_id="version-1",
            expected_examples={"task-1": "stale-example"},
        )

    asyncio.run(scenario())


def test_ensure_dataset_reuses_existing_dataset_without_uploading() -> None:
    class Datasets:
        async def get_dataset(self, **kwargs):
            assert kwargs == {"dataset": "dataset-name"}
            return SimpleNamespace(
                id="dataset-1",
                version_id="version-1",
                examples=[{"id": "example-1", "metadata": {"task_id": "task-1"}}],
            )

        async def create_dataset(self, **_kwargs):
            raise AssertionError("an existing dataset must not be uploaded again")

    async def scenario() -> None:
        sink = A2ESink.__new__(A2ESink)
        sink.client = SimpleNamespace(datasets=Datasets())
        dataset, examples = await sink.ensure_dataset(
            name="dataset-name",
            description="description",
            examples=[],
            expected_task_ids=["task-1"],
        )
        assert dataset.id == "dataset-1"
        assert examples == {"task-1": "example-1"}

    asyncio.run(scenario())


def test_ensure_dataset_uploads_when_name_is_missing() -> None:
    class Datasets:
        async def get_dataset(self, **kwargs):
            assert kwargs == {"dataset": "dataset-name"}
            raise ValueError("Dataset not found: dataset-name")

        async def create_dataset(self, **kwargs):
            assert kwargs == {
                "name": "dataset-name",
                "examples": [{"input": {"task": "task-1"}, "output": {}}],
                "dataset_description": "description",
            }
            return SimpleNamespace(
                id="dataset-1",
                version_id="version-1",
                examples=[{"id": "example-1", "metadata": {"task_id": "task-1"}}],
            )

    async def scenario() -> None:
        sink = A2ESink.__new__(A2ESink)
        sink.client = SimpleNamespace(datasets=Datasets())
        dataset, examples = await sink.ensure_dataset(
            name="dataset-name",
            description="description",
            examples=[{"input": {"task": "task-1"}, "output": {}}],
            expected_task_ids=["task-1"],
        )
        assert dataset.id == "dataset-1"
        assert examples == {"task-1": "example-1"}

    asyncio.run(scenario())


def test_experiment_recovery_uses_stable_metadata() -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        assert request.url.path == "/v1/datasets/dataset-1/experiments"
        return httpx.Response(
            200,
            json={
                "data": [
                    {
                        "id": "experiment-1",
                        "metadata": {"campaign_id": "campaign-1", "cell_id": "cell-1"},
                    }
                ],
                "next_cursor": None,
            },
        )

    async def scenario() -> None:
        sink = _sink(handler)
        try:
            found = await sink._find_experiment(
                dataset_id="dataset-1", campaign_id="campaign-1", cell_id="cell-1"
            )
            assert found == {
                "id": "experiment-1",
                "metadata": {"campaign_id": "campaign-1", "cell_id": "cell-1"},
            }
        finally:
            await sink.close()

    asyncio.run(scenario())


def test_run_409_is_read_back_before_being_accepted() -> None:
    evaluation_payloads: list[dict] = []

    def handler(request: httpx.Request) -> httpx.Response:
        if request.method == "POST" and request.url.path.endswith("/runs"):
            return httpx.Response(409, json={"detail": "already successful"})
        if request.method == "GET" and request.url.path.endswith("/runs"):
            return httpx.Response(
                200,
                json={
                    "data": [
                        {
                            "id": "run-1",
                            "dataset_example_id": "example-1",
                            "repetition_number": 1,
                            "error": None,
                        }
                    ],
                    "next_cursor": None,
                },
            )
        if request.url.path == "/v1/experiment_evaluations":
            import json

            evaluation_payloads.append(json.loads(request.content))
            return httpx.Response(200, json={"data": {"id": "evaluation-1"}})
        raise AssertionError(f"unexpected request: {request.method} {request.url}")

    async def scenario() -> None:
        now = datetime.now(timezone.utc)
        result = TrialResult(
            trial_id="trial-1",
            cell_id="cell-1",
            task_id="task-1",
            repetition=1,
            attempt=1,
            status="local_complete",
            grades=[
                GradeResult(
                    name="exact_match",
                    mode="posthoc",
                    score=1.0,
                    start_time=now,
                    end_time=now,
                )
            ],
            started_at=now,
            ended_at=now,
        )
        sink = _sink(handler)
        try:
            uploaded = await sink.upload_trial(
                result=result,
                experiment_id="experiment-1",
                dataset_example_id="example-1",
            )
            assert uploaded.status == "completed"
            assert uploaded.experiment_run_id == "run-1"
            assert evaluation_payloads[0]["experiment_run_id"] == "run-1"
        finally:
            await sink.close()

    asyncio.run(scenario())


def test_complete_ctrf_payload_is_preserved_in_experiment_run_output() -> None:
    run_payloads: list[dict] = []

    def handler(request: httpx.Request) -> httpx.Response:
        if request.method == "POST" and request.url.path.endswith("/runs"):
            import json

            run_payloads.append(json.loads(request.content))
            return httpx.Response(200, json={"data": {"id": "run-ctrf"}})
        if request.url.path == "/v1/experiment_evaluations":
            return httpx.Response(200, json={"data": {"id": "evaluation-ctrf"}})
        raise AssertionError(f"unexpected request: {request.method} {request.url}")

    async def scenario() -> None:
        now = datetime.now(timezone.utc)
        ctrf = {
            "results": {
                "summary": {"tests": 1, "passed": 1, "failed": 0},
                "tests": [{"name": "test_answer", "status": "passed"}],
            }
        }
        result = TrialResult(
            trial_id="trial-ctrf",
            cell_id="cell-1",
            task_id="task-1",
            repetition=1,
            attempt=1,
            status="local_complete",
            output={
                "tb_ctrf": ctrf,
                "tb_ctrf_artifact": {
                    "path": "verifier/ctrf.json",
                    "size_bytes": 123,
                    "sha256": "a" * 64,
                },
            },
            grades=[
                GradeResult(
                    name="terminal-bench",
                    mode="inline",
                    score=1.0,
                    start_time=now,
                    end_time=now,
                )
            ],
            started_at=now,
            ended_at=now,
        )
        sink = _sink(handler)
        try:
            await sink.upload_trial(
                result=result,
                experiment_id="experiment-1",
                dataset_example_id="example-1",
            )
        finally:
            await sink.close()

    asyncio.run(scenario())
    assert run_payloads[0]["output"]["tb_ctrf"]["results"]["tests"][0] == {
        "name": "test_answer",
        "status": "passed",
    }
