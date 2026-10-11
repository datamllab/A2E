#!/usr/bin/env python3
"""Shared trajectory evaluation core for ARCA and Docker execution paths."""

from __future__ import annotations

import importlib.util
import inspect
import json
import os
import re
import sys
from pathlib import Path
from typing import Any

import yaml
from dotenv import load_dotenv
from openai import OpenAI

import multi_judge
from transcript_normalizer import normalize_transcript_for_grader


PROJECT_ROOT = Path(__file__).resolve().parents[1]


def load_env() -> None:
    """Load environment variables from the project root .env when present."""
    env_file = PROJECT_ROOT / ".env"
    if env_file.exists():
        load_dotenv(env_file)
    else:
        load_dotenv()


def parse_transcript(session_path: str | Path) -> list[dict[str, Any]]:
    """Parse JSONL transcript records."""
    records: list[dict[str, Any]] = []
    with open(session_path, encoding="utf-8") as f:
        for line in f:
            if line.strip():
                records.append(json.loads(line))
    return records


def extract_final_response(transcript: list[dict[str, Any]]) -> str:
    """Extract the latest assistant text response from a normalized transcript."""
    for record in reversed(transcript):
        if record.get("type") != "message":
            continue
        msg = record.get("message", {})
        if msg.get("role") != "assistant":
            continue
        content = msg.get("content", [])
        if isinstance(content, list):
            for item in content:
                if item.get("type") == "text":
                    return item.get("text", "")
        if isinstance(content, str):
            return content
    return ""


def extract_user_prompt(transcript: list[dict[str, Any]]) -> str:
    """Extract the first user text prompt from a normalized transcript."""
    for record in transcript:
        if record.get("type") != "message":
            continue
        msg = record.get("message", {})
        if msg.get("role") != "user":
            continue
        content = msg.get("content", [])
        if isinstance(content, list):
            for item in content:
                if item.get("type") == "text":
                    return item.get("text", "")
        if isinstance(content, str):
            return content
    return ""


def call_grader(
    task_dir: str | Path,
    transcript: list[dict[str, Any]],
    workspace_path: str | Path,
    audit_data: dict[str, Any] | None = None,
) -> dict[str, Any]:
    """Call task-specific grader.grade()."""
    task_dir = Path(task_dir)
    grader_path = task_dir / "grader.py"
    if not grader_path.exists():
        return {"criteria": {}, "details": "No grader.py found"}

    module_name = f"_evaluation_grader_{abs(hash(str(grader_path.resolve())))}"
    task_dir_abs = str(task_dir.resolve())
    sys.path.insert(0, task_dir_abs)
    try:
        spec = importlib.util.spec_from_file_location(module_name, str(grader_path))
        if spec is None or spec.loader is None:
            return {"criteria": {}, "details": f"Could not load grader.py: {grader_path}"}
        module = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(module)
        grade = getattr(module, "grade")
        signature = inspect.signature(grade)
        if "audit_data" in signature.parameters:
            return grade(transcript, str(workspace_path), audit_data=audit_data)
        return grade(transcript, str(workspace_path))
    except Exception as exc:
        return {"criteria": {}, "details": f"Grader error: {exc}"}
    finally:
        sys.path.pop(0)


def format_judge_rubric(judge_rubric: dict[str, Any]) -> tuple[str, str]:
    """Format structured judge rubric text and expected JSON output."""
    criteria = judge_rubric.get("criteria", {})
    rubric_lines = []
    output_fields = []

    for name, criterion in criteria.items():
        weight = criterion.get("weight", 0.2)
        description = criterion.get("description", "")
        rubric_lines.append(f"**{name}** (type: weighted-sum, weight: {weight})")
        if description:
            rubric_lines.append(f"{description}")
        for level in criterion.get("rubric", []):
            if isinstance(level, dict):
                score = level.get("score", 0)
                desc = level.get("description", "")
                rubric_lines.append(f"- {score}: {desc}")
            else:
                rubric_lines.append(f"- {level}")
        rubric_lines.append("")
        output_fields.append(f'  "{name}": {{"score": <0.0-1.0>, "reason": "<brief explanation>"}}')

    rubric_text = "\n".join(rubric_lines)
    output_format = "{\n" + ",\n".join(output_fields) + "\n}"
    return rubric_text, output_format


def _extract_judge_weights(judge_rubric_text: dict[str, Any] | str) -> dict[str, float]:
    weights: dict[str, float] = {}
    if isinstance(judge_rubric_text, dict):
        for name, criterion in judge_rubric_text.get("criteria", {}).items():
            weights[name.strip()] = criterion.get("weight", 0.2)
    else:
        weight_pattern = r"\*\*([^*]+)\*\* \(type: weighted-sum, weight: ([\d.]+)\)"
        for match in re.finditer(weight_pattern, judge_rubric_text):
            weights[match.group(1).strip()] = float(match.group(2))
    return weights


def _expected_judge_criteria(judge_rubric_text: dict[str, Any] | str, judge_scores: dict[str, Any]) -> list[str]:
    if isinstance(judge_rubric_text, dict):
        return list(judge_rubric_text.get("criteria", {}).keys())
    return [key for key in judge_scores.keys() if key not in {"scores", "total", "notes"}]


def _extract_scores_payload(judge_scores: dict[str, Any], criterion_names: list[str]) -> dict[str, Any]:
    wrapper_scores = judge_scores.get("scores", {})
    if isinstance(wrapper_scores, dict) and wrapper_scores:
        return wrapper_scores

    direct_scores = {
        name: judge_scores[name]
        for name in criterion_names
        if name in judge_scores
    }
    if direct_scores:
        return direct_scores

    if "total" in judge_scores:
        return {name: judge_scores["total"] for name in criterion_names}

    return {}


def _score_value_and_details(data: Any, default_details: str = "") -> tuple[float, str]:
    details = default_details
    if isinstance(data, dict):
        details = str(data.get("reason") or data.get("details") or default_details)
        data = data.get("score", data.get("value", 0.0))
    try:
        score = float(data if data is not None else 0.0)
    except (TypeError, ValueError):
        score = 0.0
    return max(0.0, min(1.0, score)), details


def call_judge_single_model(
    judge_rubric_text: dict[str, Any] | str,
    task_prompt: str,
    agent_response: str,
    api_key: str,
    base_url: str,
    model_id: str,
    judge_config: dict[str, Any] | None = None,
) -> dict[str, Any]:
    """Call a single OpenAI-compatible judge model."""
    if isinstance(judge_rubric_text, dict):
        rubric_text, output_format = format_judge_rubric(judge_rubric_text)
    else:
        rubric_text = judge_rubric_text
        output_format = (
            "JSON object with criterion names as keys, each containing "
            "'score' (0.0-1.0) and 'reason' fields"
        )

    prompt = f"""Evaluate the agent's response based on the following rubric.

## Task

{task_prompt}

## Agent Response

{agent_response}

## Judge Rubric

{rubric_text}

Please provide your evaluation in the following JSON format:
{output_format}

Output ONLY valid JSON, no additional text."""

    client = OpenAI(api_key=api_key, base_url=base_url)

    try:
        request_cfg = dict(judge_config or {})
        request_cfg["model_id"] = model_id
        response = client.chat.completions.create(
            **multi_judge.build_chat_completion_request(
                request_cfg,
                messages=[{"role": "user", "content": prompt}],
                for_openai_sdk=True,
            )
        )
        content = response.choices[0].message.content
        if not content:
            choice = response.choices[0]
            reasoning_content = getattr(choice.message, "reasoning_content", "") or ""
            finish_reason = getattr(choice, "finish_reason", "")
            print(
                f"Judge model ({model_id}) returned empty content "
                f"(finish_reason={finish_reason}, reasoning_content_len={len(reasoning_content)})"
            )
            return {}

        cleaned = content.strip()
        if cleaned.startswith("```"):
            first_newline = cleaned.find("\n")
            cleaned = cleaned[first_newline + 1:] if first_newline != -1 else cleaned[3:]
        if cleaned.rstrip().endswith("```"):
            cleaned = cleaned.rstrip()[:-3]
        cleaned = cleaned.strip()

        try:
            judge_scores = json.loads(cleaned)
        except json.JSONDecodeError:
            json_match = re.search(r"\{.*\}", cleaned, re.DOTALL)
            if json_match:
                judge_scores = json.loads(json_match.group())
            else:
                print(f"Judge model ({model_id}) returned unparseable response: {content[:200]}")
                return {}

        weights = _extract_judge_weights(judge_rubric_text)
        criterion_names = _expected_judge_criteria(judge_rubric_text, judge_scores)
        scores = _extract_scores_payload(judge_scores, criterion_names)
        if not criterion_names:
            criterion_names = list(scores.keys())

        result = {}
        for name in criterion_names:
            data = scores.get(name, judge_scores.get(name))
            value, details = _score_value_and_details(data, str(judge_scores.get("notes", "")))
            result[name] = {
                "type": "weighted-sum",
                "value": value,
                "weight": weights.get(name, 0.2),
                "details": details,
            }
        return result
    except Exception as exc:
        print(f"Judge model ({model_id}) error: {exc}")
        return {}


def call_judge(judge_rubric_text: dict[str, Any] | str, task_prompt: str, agent_response: str) -> dict[str, Any]:
    """Backward-compatible single judge call using EVAL_JUDGE_* env vars."""
    load_env()

    api_key = os.getenv("EVAL_JUDGE_API_KEY")
    base_url = os.getenv("EVAL_JUDGE_BASE_URL")
    model_id = os.getenv("EVAL_JUDGE_MODEL_ID")

    if not all([api_key, base_url, model_id]):
        return {}

    return call_judge_single_model(
        judge_rubric_text,
        task_prompt,
        agent_response,
        api_key=api_key,
        base_url=base_url,
        model_id=model_id,
    )


def call_judge_multi_model(
    judge_rubric_text: dict[str, Any] | str,
    task_prompt: str,
    agent_response: str,
    judge_models: list[dict[str, Any]],
    aggregation_strategy: str = "weighted_average",
) -> tuple[dict[str, Any], list[dict[str, Any]]]:
    """Call multiple judge models and aggregate criterion scores."""

    def call_single(model_cfg: dict[str, Any], _run_idx: int) -> dict[str, Any]:
        return call_judge_single_model(
            judge_rubric_text,
            task_prompt,
            agent_response,
            api_key=model_cfg["api_key"],
            base_url=model_cfg["base_url"],
            model_id=model_cfg["model_id"],
            judge_config=model_cfg,
        )

    return multi_judge.run_multi_judge(
        judge_models,
        call_single,
        aggregation_strategy=aggregation_strategy,
    )


def calculate_total_score(criteria: dict[str, dict[str, Any]]) -> float:
    """Calculate overall score from criteria dict."""
    for criterion in criteria.values():
        if criterion.get("type") == "must-pass" and criterion.get("value", 1) == 0:
            return 0.0

    weighted_sum = 0.0
    total_weight = 0.0
    for criterion in criteria.values():
        if criterion.get("type") == "weighted-sum":
            weighted_sum += criterion.get("value", 0.0) * criterion.get("weight", 1.0)
            total_weight += criterion.get("weight", 1.0)

    return round(weighted_sum / total_weight, 2) if total_weight > 0 else 1.0


def _load_task_yaml(task_dir: Path) -> dict[str, Any]:
    task_yaml_path = task_dir / "task.yaml"
    if not task_yaml_path.exists():
        return {}
    with open(task_yaml_path, encoding="utf-8") as f:
        data = yaml.safe_load(f) or {}
    return data if isinstance(data, dict) else {}


def evaluate_task_trajectory(
    task_dir: str | Path,
    transcript: list[dict[str, Any]],
    workspace_path: str | Path,
    *,
    skip_judge: bool = False,
    judge_models_config: str | None = None,
    judge_base_url: str | None = None,
    judge_api_key: str | None = None,
    judge_model: str | None = None,
    audit_data: dict[str, Any] | None = None,
    trajectory_path: str = "",
) -> dict[str, Any]:
    """Evaluate one task trajectory with grader and optional judge."""
    task_dir = Path(task_dir)
    transcript = normalize_transcript_for_grader(transcript)
    agent_response = extract_final_response(transcript)
    task_prompt = extract_user_prompt(transcript)
    task_yaml = _load_task_yaml(task_dir)

    grader_result = call_grader(task_dir, transcript, workspace_path, audit_data=audit_data)
    criteria = grader_result.get("criteria", {})
    details = grader_result.get("details", "")
    if not isinstance(details, str):
        details = json.dumps(details, ensure_ascii=False)

    judge_models_used = None
    if not skip_judge and "judge_rubric" in task_yaml:
        judge_rubric_text = task_yaml.get("judge_rubric", "")
        if judge_models_config or not all([judge_base_url, judge_api_key, judge_model]):
            judge_models = multi_judge.resolve_judge_models(judge_models_config)
        else:
            judge_models = [{
                "model_id": judge_model,
                "api_key": judge_api_key,
                "base_url": judge_base_url,
                "n": 1,
                "weight": 1.0,
                "max_tokens": multi_judge.DEFAULT_JUDGE_MAX_TOKENS,
                "thinking": multi_judge.DEFAULT_JUDGE_THINKING,
                "thinking_param": multi_judge.infer_thinking_param(judge_model),
                "temperature": 0.1,
                "extra_body": {},
            }]

        if not judge_models:
            print("Warning: No judge models available — skipping judge evaluation")
        else:
            is_multi = len(judge_models) > 1 or any(m["n"] > 1 for m in judge_models)
            if is_multi:
                print(f"Calling {len(judge_models)} judge model(s) with multi-model aggregation...")
                judge_result, judge_models_used = call_judge_multi_model(
                    judge_rubric_text,
                    task_yaml.get("prompt", task_prompt),
                    agent_response,
                    judge_models=judge_models,
                )
                print(f"Judge returned {len(judge_result)} criteria (aggregated from {len(judge_models)} model(s))")
                criteria.update(judge_result)
                details += "\n\nJudge evaluation completed (multi-model)."
            else:
                model_cfg = judge_models[0]
                print(f"Calling judge model {model_cfg['model_id']}...")
                judge_result = call_judge_single_model(
                    judge_rubric_text,
                    task_yaml.get("prompt", task_prompt),
                    agent_response,
                    api_key=model_cfg["api_key"],
                    base_url=model_cfg["base_url"],
                    model_id=model_cfg["model_id"],
                    judge_config=model_cfg,
                )
                print(f"Judge returned {len(judge_result)} criteria")
                criteria.update(judge_result)
                details += "\n\nJudge evaluation completed."

    result = {
        "total_score": calculate_total_score(criteria),
        "criteria": criteria,
        "details": details,
        "agent_response_length": len(agent_response),
        "trajectory_path": trajectory_path,
    }
    if judge_models_used is not None:
        result["judge_models_used"] = judge_models_used
        result["aggregation_strategy"] = "weighted_average"
    return result


def evaluate_task_trajectory_from_path(
    task_dir: str | Path,
    trajectory_path: str | Path,
    workspace_path: str | Path,
    *,
    skip_judge: bool = False,
    judge_models_config: str | None = None,
    judge_base_url: str | None = None,
    judge_api_key: str | None = None,
    judge_model: str | None = None,
    audit_data: dict[str, Any] | None = None,
) -> dict[str, Any]:
    """Parse and evaluate one trajectory path."""
    transcript = parse_transcript(trajectory_path)
    print(f"Parsed {len(transcript)} records from trajectory")
    result = evaluate_task_trajectory(
        task_dir=task_dir,
        transcript=transcript,
        workspace_path=workspace_path,
        skip_judge=skip_judge,
        judge_models_config=judge_models_config,
        judge_base_url=judge_base_url,
        judge_api_key=judge_api_key,
        judge_model=judge_model,
        audit_data=audit_data,
        trajectory_path=str(trajectory_path),
    )
    print(f"Grader returned {len(result.get('criteria', {}))} total criteria after merge")
    return result
