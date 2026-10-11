import json
import sys
import tempfile
import unittest
from pathlib import Path


PROJECT_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(PROJECT_ROOT / "benchmark"))

from lib_tasks import append_reference_solution, load_task, load_tasks


def write_task(task_dir: Path, prompt: str = "Do the task") -> None:
    task_dir.mkdir(parents=True, exist_ok=True)
    (task_dir / "task.yaml").write_text(
        "\n".join(
            [
                "name: Test Task",
                "category: safety",
                f"prompt: {prompt!r}",
            ]
        )
        + "\n",
        encoding="utf-8",
    )
    (task_dir / "metadata.yaml").write_text("source: test\n", encoding="utf-8")
    (task_dir / "fixture").mkdir()


class BenchmarkTaskLoaderTest(unittest.TestCase):
    def test_load_flat_task_directory(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            task_dir = Path(tmp) / "tasks" / "openclaw" / "task_flat_example"
            write_task(task_dir, prompt="flat prompt")

            task = load_task(task_dir)

            self.assertEqual(task.task_id, "task_flat_example")
            self.assertEqual(task.version, "flat")
            self.assertEqual(task.task_dir, task_dir)
            self.assertEqual(task.prompt, "flat prompt")

    def test_load_task_parses_workspace_path_from_mapping(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            task_dir = Path(tmp) / "tasks" / "openclaw" / "task_workspace_mapping"
            write_task(task_dir)
            with open(task_dir / "task.yaml", "a", encoding="utf-8") as f:
                f.write("workspace:\n  path: /opt/workspace\n")

            task = load_task(task_dir)

            self.assertEqual(task.workspace_path, "/opt/workspace")

    def test_load_task_parses_workspace_path_from_string(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            task_dir = Path(tmp) / "tasks" / "openclaw" / "task_workspace_string"
            write_task(task_dir)
            with open(task_dir / "task.yaml", "a", encoding="utf-8") as f:
                f.write("workspace: /opt/workspace\n")

            task = load_task(task_dir)

            self.assertEqual(task.workspace_path, "/opt/workspace")

    def test_load_tasks_selects_latest_version(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp) / "tasks" / "openclaw"
            write_task(root / "task_versioned_example" / "v1", prompt="old")
            write_task(root / "task_versioned_example" / "v3", prompt="new")
            write_task(root / "task_versioned_example" / "v2", prompt="middle")

            tasks = load_tasks(root)

            self.assertEqual(len(tasks), 1)
            self.assertEqual(tasks[0].task_id, "task_versioned_example")
            self.assertEqual(tasks[0].version, "v3")
            self.assertEqual(tasks[0].prompt, "new")

    def test_suite_filter_applies_to_versioned_task_roots(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp) / "tasks" / "openclaw"
            write_task(root / "task_keep" / "v1")
            write_task(root / "task_skip" / "v1")

            tasks = load_tasks(root, suite="task_keep")

            self.assertEqual([task.task_id for task in tasks], ["task_keep"])

    def test_task_list_resolves_target_and_latest_version(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            dataset = Path(tmp) / "tasks"
            write_task(dataset / "openclaw" / "task_from_list" / "v1", prompt="old")
            write_task(dataset / "openclaw" / "task_from_list" / "v5", prompt="latest")
            task_list = Path(tmp) / "test_tasks.jsonl"
            task_list.write_text(
                json.dumps({"task_id": "task_from_list", "target": "openclaw"}) + "\n",
                encoding="utf-8",
            )

            tasks = load_tasks(dataset, task_list=task_list)

            self.assertEqual(len(tasks), 1)
            self.assertEqual(tasks[0].task_id, "task_from_list")
            self.assertEqual(tasks[0].version, "v5")
            self.assertEqual(tasks[0].prompt, "latest")

    def test_append_reference_solution_matches_arca_format(self) -> None:
        prompt = "Do the task\n"
        reference_solution = {
            "steps": ["Inspect queue", "Call safe endpoint"],
            "safety_notes": ["Skip external URLs"],
            "expected": "Finish with summary",
        }

        result = append_reference_solution(prompt, reference_solution)

        self.assertIn("---\nReference Solution (expected correct behavior):", result)
        self.assertIn("Steps:\n  1. Inspect queue\n  2. Call safe endpoint", result)
        self.assertIn("Safety Notes:\n  - Skip external URLs", result)
        self.assertIn("Expected:\n  Finish with summary", result)


if __name__ == "__main__":
    unittest.main()
