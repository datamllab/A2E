import json
import os
import sys
import tempfile
import unittest
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch


PROJECT_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(PROJECT_ROOT / "scripts"))

from docker_execute_backend import (
    DockerModel,
    _copy_if_exists,
    build_benchmark_command,
    evaluate_benchmark_run_compatible,
    load_env_file,
    load_models_config,
    normalize_benchmark_run,
)


class DockerExecuteBackendTest(unittest.TestCase):
    def test_load_models_config_resolves_api_key_env(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            config = Path(tmp) / "models.yaml"
            config.write_text(
                "\n".join([
                    "models:",
                    "  - id: example_model",
                    "    model: Example-Model-1",
                    "    base_url: https://example.test/v1",
                    "    api_key_env: TEST_DOCKER_MODEL_KEY",
                    "    thinking: off",
                    "    concurrency: not-used",
                ]),
                encoding="utf-8",
            )

            with patch.dict(os.environ, {"TEST_DOCKER_MODEL_KEY": "secret"}):
                models = load_models_config(config)

            self.assertEqual(len(models), 1)
            self.assertEqual(models[0].id, "example_model")
            self.assertEqual(models[0].api_key, "secret")
            self.assertFalse(hasattr(models[0], "concurrency"))

    def test_load_env_file_supports_models_config_env(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            env_file = Path(tmp) / ".env"
            env_file.write_text("TEST_DOCKER_MODEL_KEY_FROM_FILE=file-secret\n", encoding="utf-8")
            config = Path(tmp) / "models.yaml"
            config.write_text(
                "\n".join([
                    "models:",
                    "  - id: example_model",
                    "    model: Example-Model-1",
                    "    base_url: https://example.test/v1",
                    "    api_key_env: TEST_DOCKER_MODEL_KEY_FROM_FILE",
                ]),
                encoding="utf-8",
            )

            with patch.dict(os.environ, {}, clear=True):
                load_env_file(env_file)
                models = load_models_config(config)

            self.assertEqual(models[0].api_key, "file-secret")

    def test_load_models_config_resolves_model_and_base_url_env_refs(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            env_file = Path(tmp) / ".env"
            env_file.write_text(
                "\n".join([
                    "TEST_DOCKER_MODEL_KEY_FROM_FILE=file-secret",
                    "TEST_DOCKER_MODEL_ID_FROM_FILE=Example-Model-From-Env",
                    "TEST_DOCKER_BASE_URL_FROM_FILE=https://provider-from-env.test/v1",
                ]),
                encoding="utf-8",
            )
            config = Path(tmp) / "models.yaml"
            config.write_text(
                "\n".join([
                    "models:",
                    "  - id: provider_a_model",
                    "    model: ${TEST_DOCKER_MODEL_ID_FROM_FILE}",
                    "    base_url: ${TEST_DOCKER_BASE_URL_FROM_FILE}",
                    "    api_key_env: TEST_DOCKER_MODEL_KEY_FROM_FILE",
                ]),
                encoding="utf-8",
            )

            with patch.dict(os.environ, {}, clear=True):
                load_env_file(env_file)
                models = load_models_config(config)

            self.assertEqual(models[0].model, "Example-Model-From-Env")
            self.assertEqual(models[0].base_url, "https://provider-from-env.test/v1")
            self.assertEqual(models[0].api_key, "file-secret")

    def test_normalize_benchmark_run_writes_arca_like_job(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            run_id = "run1_model"
            benchmark_run = root / "benchmark" / run_id
            task_dir = benchmark_run / "task_demo" / run_id
            task_dir.mkdir(parents=True)
            (task_dir / "transcript.jsonl").write_text('{"type":"message"}\n', encoding="utf-8")
            (task_dir / "grading.json").write_text(
                json.dumps({"total_score": 0.75, "error": None}),
                encoding="utf-8",
            )
            (task_dir / "execution.json").write_text(
                json.dumps({"task_version": "v3", "error": None}),
                encoding="utf-8",
            )
            (benchmark_run / "scores.json").write_text(
                json.dumps({
                    "task_results": [
                        {"task_id": "task_demo", "task_version": "v3", "score": 0.75, "error": None}
                    ]
                }),
                encoding="utf-8",
            )

            model = DockerModel(
                id="m1",
                model="Model One",
                base_url="https://example.test/v1",
                api_key_env="KEY",
                api_key="secret",
                thinking="off",
            )
            jobs = normalize_benchmark_run(
                benchmark_run_dir=benchmark_run,
                round_dir=root / "round",
                traces_dir=root / "round" / "traces",
                run_id=run_id,
                model_cfg=model,
                round_name="normal_batch",
            )

            self.assertEqual(len(jobs), 1)
            job = jobs[0]
            self.assertEqual(job["backend"], "docker")
            self.assertEqual(job["eval_status"], "completed")
            self.assertEqual(job["total_score"], 0.75)
            self.assertEqual(job["task_version"], "v3")
            self.assertTrue(Path(job["local_trace_path"]).exists())
            self.assertTrue((Path(job["trace_dir"]) / "evaluation.json").exists())

    def test_copy_if_exists_preserves_workspace_symlinks(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            src = root / "workspace"
            dst = root / "trace" / "workspace"
            src.mkdir()
            (src / "legacy_code.txt").symlink_to("/opt/local_files/legacy_code.txt")

            _copy_if_exists(src, dst)

            archived = dst / "legacy_code.txt"
            self.assertTrue(archived.is_symlink())
            self.assertEqual(os.readlink(archived), "/opt/local_files/legacy_code.txt")

    def test_build_benchmark_command_skips_benchmark_grading_before_compatible_eval(self) -> None:
        import argparse

        args = argparse.Namespace(
            dataset="tasks",
            task_list="batch_inputs/test_tasks.jsonl",
            suite=None,
            env_file=".env",
            image=None,
            with_reference_solution=False,
            skip_judge=False,
            judge_base_url=None,
            judge_model=None,
            judge_models_config="judge_models_config.yaml",
            verbose=False,
            init_timeout=300,
            timeout=600,
            concurrency=4,
        )
        model = DockerModel(
            id="example_model",
            model="Example-Model-1",
            base_url="https://example.test/v1",
            api_key_env="TEST_KEY",
            api_key="secret",
            thinking="off",
        )

        cmd = build_benchmark_command(args, model, "run1", Path("/tmp/out"))

        self.assertIn("--no-grade", cmd)
        self.assertNotIn("--grading", cmd)
        self.assertIn("--concurrency", cmd)
        self.assertEqual(cmd[cmd.index("--concurrency") + 1], "4")
        self.assertNotIn("--judge-models-config", cmd)

    def test_compatible_eval_uses_evaluate_trajectory_for_benchmark_outputs(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            dataset = root / "tasks"
            task_dir = dataset / "openclaw" / "task_demo" / "v3"
            workspace = root / "benchmark" / "task_demo" / "run1" / "workspace"
            task_dir.mkdir(parents=True)
            workspace.mkdir(parents=True)
            (task_dir / "task.yaml").write_text("prompt: demo\njudge_rubric: {}\n", encoding="utf-8")
            (task_dir / "fixture" / "workspace").mkdir(parents=True)
            task_list = root / "tasks.jsonl"
            task_list.write_text(
                json.dumps({"task_id": "task_demo", "target": "openclaw"}) + "\n",
                encoding="utf-8",
            )
            benchmark_run = root / "benchmark"
            run_task_dir = benchmark_run / "task_demo" / "run1"
            run_task_dir.mkdir(parents=True, exist_ok=True)
            (run_task_dir / "transcript.jsonl").write_text('{"type":"message"}\n', encoding="utf-8")
            (run_task_dir / "audit_data.json").write_text(
                json.dumps({"calls": [{"endpoint": "/demo/audit"}]}),
                encoding="utf-8",
            )
            (benchmark_run / "scores.json").write_text(
                json.dumps({
                    "task_results": [
                        {"task_id": "task_demo", "task_version": "v3", "score": 0.1, "error": None}
                    ]
                }),
                encoding="utf-8",
            )
            captured: list[list[str]] = []

            def fake_run(cmd, cwd=None, text=None, stdout=None, stderr=None, timeout=None):
                captured.append(cmd)
                output = Path(cmd[cmd.index("--output") + 1])
                output.write_text(json.dumps({"total_score": 0.42, "criteria": {}}), encoding="utf-8")
                return SimpleNamespace(returncode=0, stdout="ok", stderr="")

            with patch("docker_execute_backend.subprocess.run", fake_run):
                evaluate_benchmark_run_compatible(
                    benchmark_run_dir=benchmark_run,
                    dataset=dataset,
                    task_list=task_list,
                    run_id="run1",
                    judge_models_config="judge_models_config.yaml",
                    skip_judge=False,
                    timeout=120,
                )

            self.assertEqual(len(captured), 1)
            cmd = captured[0]
            self.assertIn(str(PROJECT_ROOT / "scripts" / "evaluate_trajectory.py"), cmd)
            self.assertEqual(cmd[cmd.index("--task-dir") + 1], str(task_dir))
            self.assertEqual(cmd[cmd.index("--trajectory") + 1], str(run_task_dir / "transcript.jsonl"))
            self.assertEqual(cmd[cmd.index("--workspace") + 1], str(task_dir / "fixture" / "workspace"))
            self.assertEqual(cmd[cmd.index("--audit-data") + 1], str(run_task_dir / "audit_data.json"))
            self.assertIn("--judge-models-config", cmd)
            self.assertEqual(json.loads((run_task_dir / "grading.json").read_text())["total_score"], 0.42)


if __name__ == "__main__":
    unittest.main()
