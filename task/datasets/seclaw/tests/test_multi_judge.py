import os
import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch


PROJECT_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(PROJECT_ROOT / "scripts"))

from multi_judge import (
    aggregate_scores,
    build_chat_completion_request,
    resolve_judge_models,
    run_multi_judge,
)


class MultiJudgeTest(unittest.TestCase):
    def test_resolve_judge_models_loads_config_and_env_refs(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            config = Path(tmp) / "judge_models_config.yaml"
            config.write_text(
                "\n".join([
                    "judge_models:",
                    "  - model_id: judge-a",
                    "    api_key: ${TEST_JUDGE_KEY_A}",
                    "    base_url: https://judge-a.test/v1",
                    "    n: 2",
                    "    weight: 0.7",
                    "    max_tokens: 2048",
                    "    thinking: on",
                    "  - model_id: ${TEST_JUDGE_MODEL_B}",
                    "    api_key: literal-secret",
                    "    base_url: ${TEST_JUDGE_URL_B}",
                ]),
                encoding="utf-8",
            )

            with patch.dict(os.environ, {
                "TEST_JUDGE_KEY_A": "secret-a",
                "TEST_JUDGE_URL_B": "https://judge-b.test/v1",
                "TEST_JUDGE_MODEL_B": "judge-b",
            }):
                models = resolve_judge_models(str(config))

            self.assertEqual([m["model_id"] for m in models], ["judge-a", "judge-b"])
            self.assertEqual(models[0]["api_key"], "secret-a")
            self.assertEqual(models[0]["n"], 2)
            self.assertEqual(models[0]["weight"], 0.7)
            self.assertEqual(models[0]["max_tokens"], 2048)
            self.assertEqual(models[0]["thinking"], "on")
            self.assertEqual(models[1]["base_url"], "https://judge-b.test/v1")
            self.assertEqual(models[1]["n"], 1)
            self.assertEqual(models[1]["weight"], 1.0)
            self.assertEqual(models[1]["max_tokens"], 8192)
            self.assertEqual(models[1]["thinking"], "off")
            self.assertEqual(models[1]["thinking_param"], "enable_thinking")

    def test_build_chat_completion_request_defaults_to_thinking_off(self) -> None:
        payload = build_chat_completion_request(
            {"model_id": "judge-a"},
            messages=[{"role": "user", "content": "grade"}],
        )

        self.assertEqual(payload["max_tokens"], 8192)
        self.assertEqual(payload["enable_thinking"], False)

    def test_build_chat_completion_request_uses_openai_sdk_extra_body(self) -> None:
        kwargs = build_chat_completion_request(
            {
                "model_id": "judge-a",
                "max_tokens": 1234,
                "thinking": "on",
                "extra_body": {"top_k": 1},
            },
            messages=[{"role": "user", "content": "grade"}],
            for_openai_sdk=True,
        )

        self.assertEqual(kwargs["max_tokens"], 1234)
        self.assertNotIn("enable_thinking", kwargs)
        self.assertEqual(kwargs["extra_body"]["enable_thinking"], True)
        self.assertEqual(kwargs["extra_body"]["top_k"], 1)

    def test_qwen_models_use_chat_template_kwargs_for_thinking(self) -> None:
        payload = build_chat_completion_request(
            {"model_id": "Qwen3.5-397B-A17B", "thinking": "off"},
            messages=[{"role": "user", "content": "grade"}],
        )

        self.assertNotIn("enable_thinking", payload)
        self.assertEqual(payload["chat_template_kwargs"]["enable_thinking"], False)

    def test_qwen_openai_sdk_request_uses_nested_extra_body(self) -> None:
        kwargs = build_chat_completion_request(
            {
                "model_id": "Qwen3.5-397B-A17B",
                "thinking": "off",
                "extra_body": {"chat_template_kwargs": {"some_provider_flag": "keep"}},
            },
            messages=[{"role": "user", "content": "grade"}],
            for_openai_sdk=True,
        )

        self.assertNotIn("enable_thinking", kwargs)
        self.assertEqual(kwargs["extra_body"]["chat_template_kwargs"]["enable_thinking"], False)
        self.assertEqual(kwargs["extra_body"]["chat_template_kwargs"]["some_provider_flag"], "keep")

    def test_qwen_config_defaults_to_chat_template_kwargs_thinking_param(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            config = Path(tmp) / "judge_models_config.yaml"
            config.write_text(
                "\n".join([
                    "judge_models:",
                    "  - model_id: Qwen3.5-397B-A17B",
                    "    api_key: secret",
                    "    base_url: https://qwen.test/v1",
                ]),
                encoding="utf-8",
            )

            models = resolve_judge_models(str(config))

        self.assertEqual(models[0]["thinking"], "off")
        self.assertEqual(models[0]["thinking_param"], "chat_template_kwargs.enable_thinking")

    def test_aggregate_scores_uses_provider_average_then_provider_weight(self) -> None:
        final_score, detail = aggregate_scores({
            "judge-a": {"weight": 2.0, "scores": [0.2, 0.6], "reasons": ["a1", "a2"]},
            "judge-b": {"weight": 1.0, "scores": [1.0], "reasons": ["b1"]},
        })

        self.assertEqual(final_score, 0.6)
        self.assertEqual(detail["judge-a"]["avg_score"], 0.4)
        self.assertEqual(detail["judge-b"]["avg_score"], 1.0)

    def test_run_multi_judge_skips_failed_runs_and_keeps_metadata(self) -> None:
        judge_models = [
            {"model_id": "judge-a", "api_key": "a", "base_url": "https://a.test/v1", "n": 2, "weight": 0.5},
            {"model_id": "judge-b", "api_key": "b", "base_url": "https://b.test/v1", "n": 1, "weight": 0.5},
        ]
        calls: list[str] = []

        def call_single(model_cfg: dict, run_idx: int) -> dict:
            calls.append(f"{model_cfg['model_id']}:{run_idx}")
            if model_cfg["model_id"] == "judge-a" and run_idx == 1:
                raise RuntimeError("temporary failure")
            return {
                "quality": {
                    "type": "weighted-sum",
                    "value": 0.4 if model_cfg["model_id"] == "judge-a" else 0.8,
                    "weight": 0.3,
                    "details": f"reason from {model_cfg['model_id']}",
                }
            }

        criteria, used = run_multi_judge(judge_models, call_single)

        self.assertEqual(calls, ["judge-a:0", "judge-a:1", "judge-b:0"])
        self.assertEqual(used, [
            {"model_id": "judge-a", "n": 2, "weight": 0.5},
            {"model_id": "judge-b", "n": 1, "weight": 0.5},
        ])
        self.assertEqual(criteria["quality"]["value"], 0.6)
        self.assertEqual(criteria["quality"]["weight"], 0.3)
        self.assertEqual(criteria["quality"]["per_model"]["judge-a"]["scores"], [0.4])
        self.assertEqual(criteria["quality"]["per_model"]["judge-b"]["scores"], [0.8])


if __name__ == "__main__":
    unittest.main()
