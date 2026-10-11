import json
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path


PROJECT_ROOT = Path(__file__).resolve().parents[1]
EVALUATE_TRAJECTORY = PROJECT_ROOT / "scripts" / "evaluate_trajectory.py"


def _write_minimal_task(task_dir: Path) -> None:
    task_dir.mkdir(parents=True)
    (task_dir / "task.yaml").write_text("prompt: demo\n", encoding="utf-8")
    (task_dir / "grader.py").write_text(
        "\n".join(
            [
                "def grade(transcript, workspace_path, audit_data=None):",
                "    has_calls = bool(audit_data and audit_data.get('calls'))",
                "    return {",
                "        'criteria': {",
                "            'audit_seen': {",
                "                'type': 'weighted-sum',",
                "                'value': 1.0 if has_calls else 0.0,",
                "                'weight': 1.0,",
                "            }",
                "        },",
                "        'details': 'audit present' if has_calls else 'audit missing',",
                "    }",
            ]
        ),
        encoding="utf-8",
    )


def _write_trace(trace_dir: Path) -> Path:
    trace_dir.mkdir(parents=True)
    trajectory = trace_dir / "session_transcript.jsonl"
    trajectory.write_text(
        json.dumps(
            {
                "type": "message",
                "message": {
                    "role": "assistant",
                    "content": [{"type": "text", "text": "done"}],
                },
            }
        )
        + "\n",
        encoding="utf-8",
    )
    return trajectory


def _run_evaluation(task_dir: Path, trajectory: Path, workspace: Path, output: Path) -> dict:
    proc = subprocess.run(
        [
            sys.executable,
            str(EVALUATE_TRAJECTORY),
            "--task-dir",
            str(task_dir),
            "--trajectory",
            str(trajectory),
            "--workspace",
            str(workspace),
            "--output",
            str(output),
            "--skip-judge",
        ],
        cwd=PROJECT_ROOT,
        text=True,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        timeout=30,
    )
    if proc.returncode != 0:
        raise AssertionError(f"evaluate_trajectory failed\nSTDOUT:\n{proc.stdout}\nSTDERR:\n{proc.stderr}")
    return json.loads(output.read_text(encoding="utf-8"))


class EvaluateTrajectoryAuditDataTest(unittest.TestCase):
    def test_cli_auto_loads_audit_data_json_next_to_trajectory(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            task_dir = root / "task"
            workspace = root / "workspace"
            trace_dir = root / "trace"
            workspace.mkdir()
            _write_minimal_task(task_dir)
            trajectory = _write_trace(trace_dir)
            (trace_dir / "audit_data.json").write_text(
                json.dumps({"calls": [{"endpoint": "/social_media/post"}]}),
                encoding="utf-8",
            )

            result = _run_evaluation(task_dir, trajectory, workspace, trace_dir / "evaluation.json")

            self.assertEqual(result["total_score"], 1.0)
            self.assertEqual(result["criteria"]["audit_seen"]["value"], 1.0)

    def test_cli_auto_loads_named_service_audit_json_next_to_trajectory(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            task_dir = root / "task"
            workspace = root / "workspace"
            trace_dir = root / "trace"
            workspace.mkdir()
            _write_minimal_task(task_dir)
            trajectory = _write_trace(trace_dir)
            (trace_dir / "social_media-audit.json").write_text(
                json.dumps({"calls": [{"endpoint": "/social_media/post"}]}),
                encoding="utf-8",
            )

            result = _run_evaluation(task_dir, trajectory, workspace, trace_dir / "evaluation.json")

            self.assertEqual(result["total_score"], 1.0)
            self.assertEqual(result["criteria"]["audit_seen"]["value"], 1.0)

    def test_cli_ignores_config_audit_jsonl_when_discovering_service_audit(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            task_dir = root / "task"
            workspace = root / "workspace"
            trace_dir = root / "trace"
            workspace.mkdir()
            _write_minimal_task(task_dir)
            trajectory = _write_trace(trace_dir)
            (trace_dir / "config-audit.jsonl").write_text(
                json.dumps({"type": "config.write", "path": "openclaw.json"}) + "\n",
                encoding="utf-8",
            )

            result = _run_evaluation(task_dir, trajectory, workspace, trace_dir / "evaluation.json")

            self.assertEqual(result["total_score"], 0.0)
            self.assertEqual(result["criteria"]["audit_seen"]["value"], 0.0)


if __name__ == "__main__":
    unittest.main()
