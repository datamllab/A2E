import os
import subprocess
import tempfile
import unittest
from pathlib import Path


PROJECT_ROOT = Path(__file__).resolve().parents[1]


class BatchExecuteDockerConcurrencyTest(unittest.TestCase):
    def test_batch_runner_uses_frozen_uv_when_lockfile_exists(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            tmp_path = Path(tmp)
            tasks_jsonl = tmp_path / "tasks.jsonl"
            models_config = tmp_path / "models.yaml"
            capture_args = tmp_path / "uv_args.txt"
            fake_bin = tmp_path / "bin"
            fake_uv = fake_bin / "uv"

            tasks_jsonl.write_text('{"task_id":"task_demo","target":"openclaw"}\n', encoding="utf-8")
            models_config.write_text("models:\n  - id: fake\n", encoding="utf-8")
            fake_bin.mkdir()
            fake_uv.write_text(
                "#!/usr/bin/env bash\n"
                "printf '%s\\n' \"$@\" > \"$CAPTURE_ARGS\"\n"
                "exit 0\n",
                encoding="utf-8",
            )
            fake_uv.chmod(0o755)

            env = os.environ.copy()
            env.pop("PYTHON_CMD", None)
            env["CAPTURE_ARGS"] = str(capture_args)
            env["PATH"] = f"{fake_bin}{os.pathsep}{env['PATH']}"

            proc = subprocess.run(
                [
                    "bash",
                    "scripts/batch_execute.sh",
                    "--backend",
                    "docker",
                    "--tasks-jsonl",
                    str(tasks_jsonl),
                    "--models-config",
                    str(models_config),
                    "--batch-logs",
                    str(tmp_path / "batch_logs"),
                    "--batch-name",
                    "uv_frozen_test",
                    "--skip-analyze",
                ],
                cwd=PROJECT_ROOT,
                env=env,
                text=True,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
            )

            self.assertEqual(proc.returncode, 0, proc.stdout + proc.stderr)
            captured = capture_args.read_text(encoding="utf-8").splitlines()
            self.assertGreaterEqual(len(captured), 3)
            self.assertEqual(captured[:3], ["run", "--frozen", "python"])

    def test_docker_concurrency_cli_argument_is_passed_to_backend(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            tmp_path = Path(tmp)
            tasks_jsonl = tmp_path / "tasks.jsonl"
            models_config = tmp_path / "models.yaml"
            capture_args = tmp_path / "captured_args.txt"
            fake_python = tmp_path / "fake_python"

            tasks_jsonl.write_text('{"task_id":"task_demo","target":"openclaw"}\n', encoding="utf-8")
            models_config.write_text("models:\n  - id: fake\n", encoding="utf-8")
            fake_python.write_text(
                "#!/usr/bin/env bash\n"
                "printf '%s\\n' \"$@\" > \"$CAPTURE_ARGS\"\n"
                "exit 0\n",
                encoding="utf-8",
            )
            fake_python.chmod(0o755)

            env = os.environ.copy()
            env["PYTHON_CMD"] = str(fake_python)
            env["CAPTURE_ARGS"] = str(capture_args)

            proc = subprocess.run(
                [
                    "bash",
                    "scripts/batch_execute.sh",
                    "--backend",
                    "docker",
                    "--tasks-jsonl",
                    str(tasks_jsonl),
                    "--models-config",
                    str(models_config),
                    "--batch-logs",
                    str(tmp_path / "batch_logs"),
                    "--batch-name",
                    "docker_concurrency_test",
                    "--docker-concurrency",
                    "5",
                    "--skip-analyze",
                ],
                cwd=PROJECT_ROOT,
                env=env,
                text=True,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
            )

            self.assertEqual(proc.returncode, 0, proc.stdout + proc.stderr)
            captured = capture_args.read_text(encoding="utf-8").splitlines()
            self.assertIn("--concurrency", captured)
            self.assertEqual(captured[captured.index("--concurrency") + 1], "5")


if __name__ == "__main__":
    unittest.main()
