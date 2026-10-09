"""Idempotent adapter over the existing A2E v1 APIs."""

from __future__ import annotations

from collections.abc import Iterable
from typing import Any

import httpx

from .schema import TrialResult


class A2ESink:
    def __init__(self, *, base_url: str | None = None) -> None:
        from a2e.client import AsyncClient

        self.client = AsyncClient(base_url=base_url)

    async def close(self) -> None:
        await self.client._client.aclose()

    async def locked_dataset_exists(
        self,
        *,
        dataset_id: str,
        version_id: str,
        expected_examples: dict[str, str],
    ) -> bool:
        """Return whether one locked dataset mapping exists on this Server."""
        try:
            dataset = await self.client.datasets.get_dataset(
                dataset=dataset_id,
                version_id=version_id,
            )
        except httpx.HTTPStatusError as exc:
            if exc.response.status_code in {404, 422}:
                return False
            raise
        actual_examples = {
            str(example.get("metadata", {}).get("task_id")): str(example["id"])
            for example in dataset.examples
        }
        return (
            str(dataset.id) == dataset_id
            and str(dataset.version_id) == version_id
            and actual_examples == expected_examples
        )

    async def locked_experiment_exists(
        self,
        *,
        dataset_id: str,
        campaign_id: str,
        cell_id: str,
        experiment_id: str,
    ) -> bool:
        """Return whether one locked Cell experiment exists on this Server."""
        try:
            found = await self._find_experiment(
                dataset_id=dataset_id,
                campaign_id=campaign_id,
                cell_id=cell_id,
            )
        except httpx.HTTPStatusError as exc:
            if exc.response.status_code in {404, 422}:
                return False
            raise
        return found is not None and str(found.get("id")) == experiment_id

    async def ensure_dataset(
        self,
        *,
        name: str,
        description: str,
        examples: list[dict[str, Any]],
        expected_task_ids: Iterable[str],
    ) -> tuple[Any, dict[str, str]]:
        try:
            dataset = await self.client.datasets.get_dataset(dataset=name)
        except ValueError as exc:
            if not str(exc).startswith("Dataset not found:"):
                raise
            dataset = await self.client.datasets.create_dataset(
                name=name,
                examples=examples,
                dataset_description=description,
            )
        except httpx.HTTPStatusError as exc:
            if exc.response.status_code not in {404, 422}:
                raise
            dataset = await self.client.datasets.create_dataset(
                name=name,
                examples=examples,
                dataset_description=description,
            )
        expected = list(expected_task_ids)
        by_task_id = {
            str(example.get("metadata", {}).get("task_id")): example["id"]
            for example in dataset.examples
        }
        if set(by_task_id) != set(expected):
            raise RuntimeError(
                f"existing dataset {name!r} does not match locked task IDs"
            )
        return dataset, by_task_id

    async def ensure_experiment(
        self,
        *,
        dataset_id: str,
        dataset_version_id: str,
        name: str,
        description: str,
        metadata: dict[str, Any],
        repetitions: int,
    ) -> dict[str, Any]:
        existing = await self._find_experiment(
            dataset_id=dataset_id,
            campaign_id=str(metadata["campaign_id"]),
            cell_id=str(metadata["cell_id"]),
        )
        if existing is not None:
            return existing
        return dict(
            await self.client.experiments.create(
                dataset_id=dataset_id,
                dataset_version_id=dataset_version_id,
                experiment_name=name,
                experiment_description=description,
                experiment_metadata=metadata,
                repetitions=repetitions,
            )
        )

    async def _find_experiment(
        self, *, dataset_id: str, campaign_id: str, cell_id: str
    ) -> dict[str, Any] | None:
        cursor: str | None = None
        matches: list[dict[str, Any]] = []
        while True:
            params: dict[str, Any] = {"limit": 100}
            if cursor:
                params["cursor"] = cursor
            response = await self.client._client.get(
                f"v1/datasets/{dataset_id}/experiments", params=params
            )
            response.raise_for_status()
            body = response.json()
            for experiment in body.get("data", []):
                metadata = experiment.get("metadata") or {}
                if (
                    metadata.get("campaign_id") == campaign_id
                    and metadata.get("cell_id") == cell_id
                ):
                    matches.append(experiment)
            cursor = body.get("next_cursor")
            if not cursor:
                break
        if len(matches) > 1:
            raise RuntimeError(
                f"multiple experiments match campaign={campaign_id} cell={cell_id}"
            )
        return matches[0] if matches else None

    async def upload_trial(
        self,
        *,
        result: TrialResult,
        experiment_id: str,
        dataset_example_id: str,
    ) -> TrialResult:
        result = result.model_copy(update={"status": "uploading"})
        run_payload = {
            "dataset_example_id": dataset_example_id,
            "output": result.output,
            "repetition_number": result.repetition,
            "start_time": result.started_at.isoformat(),
            "end_time": result.ended_at.isoformat(),
            "trace_id": result.trace_id,
            "error": result.error,
        }
        run_id: str | None = None
        try:
            response = await self.client._client.post(
                f"v1/experiments/{experiment_id}/runs", json=run_payload
            )
            response.raise_for_status()
            run_id = response.json()["data"]["id"]
        except httpx.HTTPStatusError as exc:
            if exc.response.status_code != 409:
                raise
            run_id = await self._resolve_existing_run(
                experiment_id=experiment_id,
                dataset_example_id=dataset_example_id,
                repetition=result.repetition,
            )
            if run_id is None:
                raise RuntimeError(
                    "server returned 409 but the successful run could not be reconciled"
                ) from exc

        for grade in result.grades:
            payload: dict[str, Any] = {
                "experiment_run_id": run_id,
                "name": grade.name,
                "annotator_kind": grade.annotator_kind,
                "start_time": grade.start_time.isoformat(),
                "end_time": grade.end_time.isoformat(),
                "metadata": {
                    **grade.metadata,
                    "mode": grade.mode,
                    "required": grade.required,
                },
                "trace_id": grade.trace_id,
            }
            if grade.error:
                payload["error"] = grade.error
            else:
                payload["result"] = {
                    "score": grade.score,
                    "label": grade.label,
                    "explanation": grade.explanation,
                }
            response = await self.client._client.post(
                "v1/experiment_evaluations", json=payload
            )
            response.raise_for_status()
        terminal_status = "completed" if result.error is None else "failed"
        return result.model_copy(
            update={
                "status": terminal_status,
                "uploaded": True,
                "experiment_run_id": run_id,
            }
        )

    async def _resolve_existing_run(
        self, *, experiment_id: str, dataset_example_id: str, repetition: int
    ) -> str | None:
        cursor: str | None = None
        while True:
            params: dict[str, Any] = {"limit": 100}
            if cursor:
                params["cursor"] = cursor
            response = await self.client._client.get(
                f"v1/experiments/{experiment_id}/runs", params=params
            )
            response.raise_for_status()
            body = response.json()
            for run in body.get("data", []):
                if (
                    run.get("dataset_example_id") == dataset_example_id
                    and run.get("repetition_number") == repetition
                    and run.get("error") is None
                ):
                    return str(run["id"])
            cursor = body.get("next_cursor")
            if not cursor:
                return None
