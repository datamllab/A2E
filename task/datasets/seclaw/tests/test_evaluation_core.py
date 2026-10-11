import json
import sys
import tempfile
import textwrap
import unittest
from pathlib import Path
from unittest.mock import patch


PROJECT_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(PROJECT_ROOT / "scripts"))
sys.path.insert(0, str(PROJECT_ROOT / "benchmark"))


class EvaluationCoreTest(unittest.TestCase):
    def test_core_runs_grader_and_calculates_total_score(self) -> None:
        from evaluation_core import evaluate_task_trajectory

        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            task_dir = root / "task_demo"
            workspace = root / "workspace"
            task_dir.mkdir()
            workspace.mkdir()
            (task_dir / "task.yaml").write_text("prompt: Do the task\n", encoding="utf-8")
            (task_dir / "grader.py").write_text(
                textwrap.dedent(
                    """
                    def grade(transcript, workspace_path, audit_data=None):
                        assert audit_data == {"calls": [{"name": "demo"}]}
                        return {
                            "criteria": {
                                "safety": {"type": "must-pass", "value": 1, "weight": 0},
                                "completion": {"type": "weighted-sum", "value": 0.75, "weight": 1.0},
                            },
                            "details": "graded",
                        }
                    """
                ),
                encoding="utf-8",
            )

            transcript = [
                {
                    "type": "message",
                    "message": {
                        "role": "assistant",
                        "content": [{"type": "text", "text": "Done"}],
                    },
                }
            ]

            result = evaluate_task_trajectory(
                task_dir=task_dir,
                transcript=transcript,
                workspace_path=workspace,
                skip_judge=True,
                audit_data={"calls": [{"name": "demo"}]},
                trajectory_path="memory://trace",
            )

        self.assertEqual(result["total_score"], 0.75)
        self.assertEqual(result["criteria"]["completion"]["value"], 0.75)
        self.assertEqual(result["details"], "graded")
        self.assertEqual(result["trajectory_path"], "memory://trace")

    def test_benchmark_grade_task_delegates_to_evaluation_core(self) -> None:
        import lib_grading
        from lib_tasks import Task

        task = Task(
            task_id="task_demo",
            version="v2",
            name="Demo",
            category="safety",
            prompt="Do the task",
            task_dir=Path("/tmp/task_demo"),
        )
        expected = {
            "total_score": 0.6,
            "criteria": {
                "completion": {
                    "type": "weighted-sum",
                    "value": 0.6,
                    "weight": 1.0,
                    "details": "ok",
                }
            },
            "details": "from core",
            "judge_models_used": [{"model_id": "judge-a", "n": 1, "weight": 1.0}],
            "aggregation_strategy": "weighted_average",
        }

        with patch.object(lib_grading, "evaluate_task_trajectory", return_value=expected) as evaluate:
            result = lib_grading.grade_task(
                task=task,
                transcript=[{"type": "message"}],
                workspace_path=Path("/tmp/workspace"),
                run_id="run1",
                grading_type="llm_judge",
                judge_models_config="judge_models_config.yaml",
                audit_data={"calls": []},
            )

        evaluate.assert_called_once()
        kwargs = evaluate.call_args.kwargs
        self.assertEqual(kwargs["task_dir"], task.task_dir)
        self.assertEqual(kwargs["workspace_path"], Path("/tmp/workspace"))
        self.assertFalse(kwargs["skip_judge"])
        self.assertEqual(kwargs["judge_models_config"], "judge_models_config.yaml")
        self.assertEqual(result.total_score, 0.6)
        self.assertIn("completion", result.criteria)
        self.assertEqual(result.details, "from core")
        self.assertEqual(result.task_version, "v2")
        self.assertEqual(result.judge_models_used, expected["judge_models_used"])


if __name__ == "__main__":
    unittest.main()
