"""Shared multi-judge-model orchestration utilities.

This module owns provider config loading, repeated judge calls, and
cross-provider weighted aggregation. Entry points remain responsible for
building prompts and converting their local criterion/result types.
"""

from __future__ import annotations

import json
import os
import re
from pathlib import Path
from typing import Any, Callable

import yaml


PROJECT_ROOT = Path(__file__).resolve().parents[1]
DEFAULT_JUDGE_MAX_TOKENS = 8192
DEFAULT_JUDGE_THINKING = "off"
DEFAULT_THINKING_PARAM = "enable_thinking"
QWEN_THINKING_PARAM = "chat_template_kwargs.enable_thinking"


def resolve_env_vars(value: str) -> str:
    """Resolve ${VAR_NAME} references in a string."""
    if not isinstance(value, str):
        return value

    pattern = re.compile(r"\$\{([^}]+)\}")

    def _replace(match: re.Match[str]) -> str:
        var_name = match.group(1)
        env_value = os.environ.get(var_name)
        if env_value is not None:
            return env_value
        print(f"Warning: Environment variable '{var_name}' is not set, keeping '${{{var_name}}}' as-is")
        return match.group(0)

    return pattern.sub(_replace, value)


def resolve_config_value(value: Any) -> Any:
    """Resolve ${VAR_NAME} references recursively in config values."""
    if isinstance(value, dict):
        return {k: resolve_config_value(v) for k, v in value.items()}
    if isinstance(value, list):
        return [resolve_config_value(v) for v in value]
    return resolve_env_vars(value)


def normalize_thinking(value: Any) -> str:
    """Normalize provider thinking config to 'on', 'off', or 'default'."""
    if value is None:
        return DEFAULT_JUDGE_THINKING
    if isinstance(value, bool):
        return "on" if value else "off"

    text = str(value).strip().lower()
    if text in {"1", "true", "yes", "on", "enable", "enabled"}:
        return "on"
    if text in {"0", "false", "no", "off", "disable", "disabled"}:
        return "off"
    if text in {"default", "provider_default", "none", "null"}:
        return "default"
    return text


def _thinking_bool(thinking: str) -> bool | None:
    normalized = normalize_thinking(thinking)
    if normalized == "on":
        return True
    if normalized == "off":
        return False
    return None


def infer_thinking_param(model_id: str | None) -> str:
    """Infer the provider-specific thinking control key for known models."""
    model_name = (model_id or "").lower()
    if "qwen" in model_name or "qwq" in model_name:
        return QWEN_THINKING_PARAM
    return DEFAULT_THINKING_PARAM


def _set_extra_body_default(extra_body: dict, dotted_key: str, value: Any) -> None:
    """Set a provider extra_body default, supporting dotted nested paths."""
    parts = [part.strip() for part in dotted_key.split(".") if part.strip()]
    if not parts:
        return

    current = extra_body
    for part in parts[:-1]:
        nested = current.get(part)
        if not isinstance(nested, dict):
            nested = {}
            current[part] = nested
        current = nested
    current.setdefault(parts[-1], value)


def build_chat_completion_request(
    model_cfg: dict,
    messages: list[dict],
    *,
    temperature: float = 0.1,
    for_openai_sdk: bool = False,
) -> dict:
    """Build an OpenAI-compatible chat completion request.

    Raw HTTP callers receive provider-specific fields merged into the JSON
    payload. OpenAI SDK callers receive those fields under ``extra_body``.
    """
    model_id = model_cfg.get("model_id") or model_cfg.get("model")
    payload = {
        "model": model_id,
        "messages": messages,
        "temperature": float(model_cfg.get("temperature", temperature)),
        "max_tokens": int(model_cfg.get("max_tokens", DEFAULT_JUDGE_MAX_TOKENS)),
    }

    extra_body = dict(model_cfg.get("extra_body") or {})
    thinking = normalize_thinking(model_cfg.get("thinking", DEFAULT_JUDGE_THINKING))
    thinking_param = str(model_cfg.get("thinking_param") or infer_thinking_param(model_id)).strip()
    thinking_enabled = _thinking_bool(thinking)
    if thinking_enabled is not None and thinking_param.lower() not in {"", "none", "false", "off"}:
        _set_extra_body_default(extra_body, thinking_param, thinking_enabled)

    if for_openai_sdk:
        if extra_body:
            payload["extra_body"] = extra_body
    else:
        payload.update(extra_body)

    return payload


def load_judge_models_config(config_path: str | Path) -> list[dict]:
    """Load judge model configurations from a JSON or YAML file."""
    path = Path(config_path)
    if not path.exists():
        raise FileNotFoundError(f"Judge models config file not found: {config_path}")

    with open(path, encoding="utf-8") as f:
        if path.suffix in (".yaml", ".yml"):
            config = yaml.safe_load(f)
        else:
            config = json.load(f)

    if not config or "judge_models" not in config:
        raise ValueError(f"Config file must contain a 'judge_models' key: {config_path}")

    raw_models = config["judge_models"]
    if not isinstance(raw_models, list) or not raw_models:
        raise ValueError(f"'judge_models' must be a non-empty list: {config_path}")

    result = []
    for i, entry in enumerate(raw_models):
        model_id = resolve_env_vars(str(entry.get("model_id", "")))
        if not model_id:
            raise ValueError(f"judge_models[{i}]: 'model_id' is required")

        api_key_raw = entry.get("api_key", "")
        base_url_raw = entry.get("base_url", "")
        api_key = resolve_env_vars(str(api_key_raw))
        base_url = resolve_env_vars(str(base_url_raw))

        if not api_key:
            raise ValueError(
                f"judge_models[{i}] ({model_id}): 'api_key' resolves to empty (raw: {api_key_raw})"
            )
        if not base_url:
            raise ValueError(
                f"judge_models[{i}] ({model_id}): 'base_url' resolves to empty (raw: {base_url_raw})"
            )

        result.append({
            "model_id": model_id,
            "api_key": api_key,
            "base_url": base_url,
            "n": int(entry.get("n", 1)),
            "weight": float(entry.get("weight", 1.0)),
            "max_tokens": int(entry.get("max_tokens", DEFAULT_JUDGE_MAX_TOKENS)),
            "thinking": normalize_thinking(entry.get("thinking", DEFAULT_JUDGE_THINKING)),
            "thinking_param": str(entry.get("thinking_param") or infer_thinking_param(model_id)),
            "temperature": float(entry.get("temperature", 0.1)),
            "extra_body": resolve_config_value(entry.get("extra_body", {})) or {},
        })

    return result


def default_judge_models_config_path() -> str | None:
    """Return the default project-root judge models config path if present."""
    for name in ("judge_models_config.yaml", "judge_models_config.yml", "judge_models_config.json"):
        candidate = PROJECT_ROOT / name
        if candidate.exists():
            return str(candidate)
    return None


def resolve_judge_models(config_path: str | None = None) -> list[dict]:
    """Resolve judge model configs from an explicit/default config or env fallback."""
    if config_path:
        return load_judge_models_config(config_path)

    default_path = default_judge_models_config_path()
    if default_path:
        print(f"Using judge models config: {default_path}")
        return load_judge_models_config(default_path)

    api_key = os.getenv("EVAL_JUDGE_API_KEY")
    base_url = os.getenv("EVAL_JUDGE_BASE_URL")
    model_id = os.getenv("EVAL_JUDGE_MODEL_ID")
    if not all([api_key, base_url, model_id]):
        return []

    return [{
        "model_id": model_id,
        "api_key": api_key,
        "base_url": base_url,
        "n": 1,
        "weight": 1.0,
        "max_tokens": DEFAULT_JUDGE_MAX_TOKENS,
        "thinking": DEFAULT_JUDGE_THINKING,
        "thinking_param": infer_thinking_param(model_id),
        "temperature": 0.1,
        "extra_body": {},
    }]


def aggregate_scores(
    model_results: dict[str, dict],
    strategy: str = "weighted_average",
) -> tuple[float, dict]:
    """Aggregate per-provider repeated scores for one criterion."""
    per_model_detail = {}
    for model_id, info in model_results.items():
        scores = info.get("scores", [])
        avg = sum(scores) / len(scores) if scores else 0.0
        per_model_detail[model_id] = {
            "weight": info.get("weight", 1.0),
            "scores": scores,
            "avg_score": round(avg, 4),
            "reasons": info.get("reasons", []),
        }

    if strategy != "weighted_average":
        raise ValueError(f"Unknown aggregation strategy: {strategy}")

    total_weight = sum(d["weight"] for d in per_model_detail.values() if d["scores"])
    if total_weight == 0:
        return 0.0, per_model_detail
    weighted_sum = sum(
        d["avg_score"] * d["weight"]
        for d in per_model_detail.values()
        if d["scores"]
    )
    return round(weighted_sum / total_weight, 4), per_model_detail


def run_multi_judge(
    judge_models: list[dict],
    call_single_model: Callable[[dict, int], dict],
    aggregation_strategy: str = "weighted_average",
) -> tuple[dict, list[dict]]:
    """Call multiple judge models and aggregate criteria.

    ``call_single_model`` receives ``(model_cfg, run_idx)`` and returns a
    criteria dict keyed by criterion name.
    """
    model_raw: dict[str, dict[str, dict]] = {}
    model_succeeded: dict[str, bool] = {}
    judge_models_used = []

    for model_cfg in judge_models:
        model_id = model_cfg["model_id"]
        n = int(model_cfg.get("n", 1))
        weight = float(model_cfg.get("weight", 1.0))
        judge_models_used.append({"model_id": model_id, "n": n, "weight": weight})

        model_raw[model_id] = {}
        success_count = 0
        for run_idx in range(n):
            print(f"  Calling judge model {model_id} (run {run_idx + 1}/{n})...")
            try:
                result = call_single_model(model_cfg, run_idx)
            except Exception as exc:
                print(f"  Warning: Judge model {model_id} run {run_idx + 1} failed: {exc}")
                continue
            if not result:
                print(f"  Warning: Judge model {model_id} run {run_idx + 1} returned empty result")
                continue

            success_count += 1
            for criterion_name, criterion_data in result.items():
                model_raw[model_id].setdefault(criterion_name, {"scores": [], "reasons": [], "weight": None})
                model_raw[model_id][criterion_name]["scores"].append(criterion_data.get("value", 0.0))
                model_raw[model_id][criterion_name]["reasons"].append(criterion_data.get("details", ""))
                if model_raw[model_id][criterion_name]["weight"] is None:
                    model_raw[model_id][criterion_name]["weight"] = criterion_data.get("weight", 0.2)

        model_succeeded[model_id] = success_count > 0
        if success_count == 0:
            print(f"  Warning: Judge model {model_id} produced no successful results across {n} run(s)")

    succeeded_models = [m for m, ok in model_succeeded.items() if ok]
    if not succeeded_models:
        print("  Warning: All judge models failed - returning empty judge criteria")
        return {}, judge_models_used

    all_criteria_names: set[str] = set()
    criterion_weights: dict[str, float] = {}
    for model_id, criteria_data in model_raw.items():
        if not model_succeeded.get(model_id):
            continue
        all_criteria_names.update(criteria_data.keys())
        for criterion_name, data in criteria_data.items():
            if criterion_name not in criterion_weights and data.get("weight") is not None:
                criterion_weights[criterion_name] = float(data["weight"])

    criteria = {}
    total_models = len(succeeded_models)
    total_runs = sum(int(m.get("n", 1)) for m in judge_models if m["model_id"] in succeeded_models)
    is_multi = len(judge_models) > 1 or any(int(m.get("n", 1)) > 1 for m in judge_models)

    for criterion_name in sorted(all_criteria_names):
        model_results_for_criterion: dict[str, dict] = {}
        for model_cfg in judge_models:
            model_id = model_cfg["model_id"]
            if not model_succeeded.get(model_id):
                continue
            if criterion_name not in model_raw.get(model_id, {}):
                continue
            model_results_for_criterion[model_id] = {
                "weight": float(model_cfg.get("weight", 1.0)),
                "scores": model_raw[model_id][criterion_name]["scores"],
                "reasons": model_raw[model_id][criterion_name]["reasons"],
            }

        if not model_results_for_criterion:
            continue

        final_score, per_model_detail = aggregate_scores(
            model_results_for_criterion,
            strategy=aggregation_strategy,
        )
        criterion_entry = {
            "type": "weighted-sum",
            "value": final_score,
            "weight": criterion_weights.get(criterion_name, 0.2),
            "details": f"Judge evaluation ({total_models} model(s), {total_runs} run(s))",
        }
        if is_multi:
            criterion_entry["per_model"] = per_model_detail
        criteria[criterion_name] = criterion_entry

    return criteria, judge_models_used
