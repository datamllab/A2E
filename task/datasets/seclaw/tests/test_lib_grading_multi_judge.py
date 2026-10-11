import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch


PROJECT_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(PROJECT_ROOT / "benchmark"))

from lib_grading import grade_llm_judge, grade_task
from lib_tasks import JudgeRubric, JudgeRubricCriterion, Task


class LibGradingMultiJudgeTest(unittest.TestCase):
    def make_task(self, task_dir: Path) -> Task:
        return Task(
            task_id="task_demo",
            version="v1",
            name="Demo",
            category="safety",
            prompt="Do the safe thing.",
            task_dir=task_dir,
            judge_rubric=JudgeRubric(
                model="",
                api_base="",
                criteria={
                    "quality": JudgeRubricCriterion(
                        description="Quality",
                        weight=0.4,
                        rubric=[{"score": 1, "description": "Good"}],
                    )
                },
            ),
        )

    def test_grade_task_uses_shared_evaluation_core(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            task_dir = Path(tmp) / "task_demo"
            workspace = Path(tmp) / "workspace"
            task_dir.mkdir()
            workspace.mkdir()
            task = self.make_task(task_dir)
            transcript = [
                {"type": "message", "message": {"role": "assistant", "content": [{"type": "text", "text": "Done"}]}}
            ]

            core_result = {
                "total_score": 0.75,
                "criteria": {
                    "quality": {
                        "type": "weighted-sum",
                        "value": 0.75,
                        "weight": 0.4,
                        "details": "aggregated",
                        "per_model": {"judge-a": {"scores": [0.7, 0.8], "avg_score": 0.75, "weight": 0.5}},
                    },
                },
                "details": "Judge evaluation completed (multi-model).",
                "judge_models_used": [{"model_id": "judge-a", "n": 2, "weight": 0.5}],
                "aggregation_strategy": "weighted_average",
            }

            with patch("lib_grading.evaluate_task_trajectory", return_value=core_result) as evaluate:
                result = grade_task(
                    task=task,
                    transcript=transcript,
                    workspace_path=workspace,
                    grading_type="llm_judge",
                    judge_models_config="judge_models_config.yaml",
                )

            evaluate.assert_called_once()
            self.assertIn("quality", result.criteria)
            self.assertEqual(result.criteria["quality"].value, 0.75)
            self.assertAlmostEqual(result.total_score, 0.75)
            self.assertEqual(result.judge_models_used, [{"model_id": "judge-a", "n": 2, "weight": 0.5}])
            self.assertEqual(result.aggregation_strategy, "weighted_average")

    def test_grade_task_rejects_removed_hybrid_mode(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            task_dir = Path(tmp) / "task_demo"
            workspace = Path(tmp) / "workspace"
            task_dir.mkdir()
            workspace.mkdir()
            task = self.make_task(task_dir)

            with self.assertRaisesRegex(ValueError, "Unsupported grading_type"):
                grade_task(
                    task=task,
                    transcript=[],
                    workspace_path=workspace,
                    grading_type="hybrid",
                )

    def test_grade_llm_judge_accepts_top_level_criteria_json_and_uses_request_options(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            task_dir = Path(tmp) / "task_demo"
            task_dir.mkdir()
            task = self.make_task(task_dir)
            transcript = [
                {"type": "message", "message": {"role": "assistant", "content": [{"type": "text", "text": "Done"}]}}
            ]
            captured_payload = {}

            class FakeResponse:
                def raise_for_status(self) -> None:
                    return None

                def json(self) -> dict:
                    return {
                        "choices": [
                            {
                                "message": {
                                    "content": '{"quality": {"score": 0.7, "reason": "mostly good"}}'
                                }
                            }
                        ]
                    }

            class FakeClient:
                def __init__(self, *args, **kwargs) -> None:
                    pass

                def __enter__(self):
                    return self

                def __exit__(self, *args) -> None:
                    return None

                def post(self, url, headers=None, json=None):
                    captured_payload.update(json)
                    return FakeResponse()

            with patch("lib_grading.httpx.Client", FakeClient):
                result = grade_llm_judge(
                    task=task,
                    transcript=transcript,
                    judge_base_url="https://judge.test/v1",
                    judge_api_key="secret",
                    judge_model="judge-a",
                    judge_config={"max_tokens": 2048, "thinking": "off"},
                )

            self.assertEqual(captured_payload["max_tokens"], 2048)
            self.assertEqual(captured_payload["enable_thinking"], False)
            self.assertEqual(result["quality"].value, 0.7)
            self.assertEqual(result["quality"].details, "mostly good")

    def test_qwen_judge_payload_uses_chat_template_kwargs_for_thinking(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            task_dir = Path(tmp) / "task_demo"
            task_dir.mkdir()
            task = self.make_task(task_dir)
            transcript = [
                {"type": "message", "message": {"role": "assistant", "content": [{"type": "text", "text": "Done"}]}}
            ]
            captured_payload = {}

            class FakeResponse:
                def raise_for_status(self) -> None:
                    return None

                def json(self) -> dict:
                    return {
                        "choices": [
                            {
                                "message": {
                                    "content": '{"quality": {"score": 0.7, "reason": "mostly good"}}'
                                }
                            }
                        ]
                    }

            class FakeClient:
                def __init__(self, *args, **kwargs) -> None:
                    pass

                def __enter__(self):
                    return self

                def __exit__(self, *args) -> None:
                    return None

                def post(self, url, headers=None, json=None):
                    captured_payload.update(json)
                    return FakeResponse()

            with patch("lib_grading.httpx.Client", FakeClient):
                result = grade_llm_judge(
                    task=task,
                    transcript=transcript,
                    judge_base_url="https://judge.test/v1",
                    judge_api_key="secret",
                    judge_model="Qwen3.5-397B-A17B",
                    judge_config={"max_tokens": 2048, "thinking": "off"},
                )

            self.assertNotIn("enable_thinking", captured_payload)
            self.assertEqual(
                captured_payload["chat_template_kwargs"]["enable_thinking"],
                False,
            )
            self.assertEqual(result["quality"].value, 0.7)


if __name__ == "__main__":
    unittest.main()
