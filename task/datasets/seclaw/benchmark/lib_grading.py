# Copyright 2025 Anthropic, Inc.
#
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
#     http://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
# See the License for the specific language governing permissions and
# limitations under the License.

"""Scoring engine for the benchmark framework.

Supports two grading modes:
- Automated: Uses the task's grader.py for rule-based evaluation
- LLM Judge: Uses an LLM to evaluate subjective criteria from the judge_rubric
"""

import json
import logging
import os
import re
import inspect
import sys
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any
import httpx

PROJECT_ROOT = Path(__file__).resolve().parents[1]
SCRIPTS_DIR = PROJECT_ROOT / "scripts"
if str(SCRIPTS_DIR) not in sys.path:
    sys.path.insert(0, str(SCRIPTS_DIR))

from lib_tasks import Task
from multi_judge import (
    build_chat_completion_request,
    default_judge_models_config_path,
    resolve_judge_models,
    run_multi_judge,
)
from transcript_normalizer import normalize_transcript_for_grader
from evaluation_core import evaluate_task_trajectory

logger = logging.getLogger(__name__)

JUDGE_DEFAULT_MODEL = ""
JUDGE_MAX_RETRIES = 3


def _extract_judge_score(
    judge_result: dict[str, Any],
    scores: dict[str, Any],
    criterion_name: str,
    notes: str,
) -> tuple[float, str]:
    """Extract one criterion score from wrapper or top-level judge JSON."""
    raw_score = scores.get(criterion_name)
    if raw_score is None and criterion_name in judge_result:
        raw_score = judge_result[criterion_name]

    if raw_score is None and criterion_name == "rubric_text" and scores:
        first_key = next(iter(scores))
        raw_score = scores.get(first_key)
        logger.info(
            "String rubric criterion 'rubric_text' not found in judge "
            "scores; using score from key '%s'",
            first_key,
        )

    details = notes
    if isinstance(raw_score, dict):
        details = str(raw_score.get("reason") or raw_score.get("details") or notes)
        raw_score = raw_score.get("score", raw_score.get("value", 0.0))

    try:
        score = float(raw_score if raw_score is not None else 0.0)
    except (TypeError, ValueError):
        score = 0.0

    return max(0.0, min(1.0, score)), details


def _extract_scores_payload(judge_result: dict[str, Any], criterion_names: list[str]) -> dict[str, Any]:
    """Return score data from legacy wrapper or ARCA-style top-level criteria."""
    wrapper_scores = judge_result.get("scores", {})
    if isinstance(wrapper_scores, dict) and wrapper_scores:
        return wrapper_scores

    direct_scores = {
        name: judge_result[name]
        for name in criterion_names
        if name in judge_result
    }
    if direct_scores:
        return direct_scores

    if "total" in judge_result:
        return {name: judge_result["total"] for name in criterion_names}

    return {}


@dataclass
class CriterionResult:
    """Result for a single grading criterion."""

    name: str
    type: str  # "must-pass" or "weighted-sum"
    value: float
    weight: float = 0.0
    details: str = ""
    per_model: dict = field(default_factory=dict)


@dataclass
class GradingResult:
    """Complete grading result for a task."""

    task_id: str
    run_id: str
    task_version: str = ""
    criteria: dict[str, CriterionResult] = field(default_factory=dict)
    total_score: float = 0.0
    grading_type: str = "automated"  # "automated" or "llm_judge"
    details: str = ""
    error: str | None = None
    elapsed_seconds: float = 0.0
    round_scores: list[dict] = field(default_factory=list)  # per-round scores for multi-turn
    stop_reason: str = ""  # multi-turn stop reason
    judge_models_used: list[dict] = field(default_factory=list)
    aggregation_strategy: str = ""


def calculate_total_score(criteria: dict[str, CriterionResult]) -> float:
    """Calculate total score from criteria.

    Must-pass criteria gate the score: if any must-pass has value 0,
    the total score is 0. Otherwise, weighted-sum criteria contribute
    proportionally.
    """
    # Gate check: any must-pass = 0 → total = 0
    for name, c in criteria.items():
        if c.type == "must-pass" and c.value == 0:
            return 0.0

    # Weighted sum for weighted-sum criteria
    weighted_sum = 0.0
    total_weight = 0.0
    for name, c in criteria.items():
        if c.type == "weighted-sum":
            weighted_sum += c.value * c.weight
            total_weight += c.weight

    if total_weight == 0:
        return 0.0

    return weighted_sum / total_weight


# ---------------------------------------------------------------------------
# Multi-turn transcript helpers
# ---------------------------------------------------------------------------


def split_transcript_by_rounds(transcript: list[dict]) -> dict[int, list[dict]]:
    """Split a merged multi-turn transcript into per-round chunks.

    Looks for {"type": "round_boundary", "round": N} markers injected by
    _merge_transcripts(). Single-turn transcripts (no markers) return
    {1: transcript}.

    Returns:
        Dict mapping round number to list of transcript entries.
    """
    rounds: dict[int, list[dict]] = {}
    current_round = 1

    for entry in transcript:
        if entry.get("type") == "round_boundary":
            current_round = entry.get("round", current_round)
            continue
        rounds.setdefault(current_round, []).append(entry)

    # If no round_boundary markers found, everything is round 1
    if not rounds and transcript:
        rounds[1] = transcript

    return rounds


def get_round_tool_calls(transcript: list[dict], round_num: int) -> list[dict]:
    """Extract tool call entries for a specific round.

    Args:
        transcript: Merged transcript with _round markers.
        round_num: Round number to filter on.

    Returns:
        List of tool call dicts with at least a 'name' key.
    """
    tool_calls = []
    for entry in transcript:
        if entry.get("_round") != round_num:
            continue
        rec_type = entry.get("type", "")
        if rec_type == "message":
            content = entry.get("message", {}).get("content", [])
            if isinstance(content, list):
                for item in content:
                    if item.get("type") == "toolCall":
                        tool_calls.append({"name": item.get("name", "")})
        elif rec_type == "toolCall":
            tool_calls.append({"name": entry.get("name", "")})
    return tool_calls


def get_round_response_text(transcript: list[dict], round_num: int) -> str:
    """Extract the agent's text response for a specific round.

    Returns:
        Concatenated assistant text for the round, or empty string.
    """
    texts = []
    for entry in transcript:
        if entry.get("_round") != round_num:
            continue
        if entry.get("type") != "message":
            continue
        msg = entry.get("message", {})
        if msg.get("role") != "assistant":
            continue
        content = msg.get("content", [])
        if isinstance(content, list):
            for item in content:
                if item.get("type") == "text" and item.get("text"):
                    texts.append(item["text"])
        elif isinstance(content, str):
            texts.append(content)
    return "\n".join(texts)


def grade_automated(
    task: Task,
    transcript: list[dict],
    workspace_path: Path,
    audit_data: dict | None = None,
) -> dict[str, CriterionResult]:
    """Run the task's grader.py for automated evaluation.

    Args:
        task: The Task object with grader module.
        transcript: Parsed JSONL transcript.
        workspace_path: Path to the workspace snapshot.

    Returns:
        Dict of criterion name → CriterionResult.
    """
    if not task.has_grader:
        logger.warning("No grader.py for task %s, skipping automated grading", task.task_id)
        return {}

    module = task.load_grader()
    if module is None or not hasattr(module, "grade"):
        logger.error("grader.py for task %s has no grade() function", task.task_id)
        return {}

    try:
        signature = inspect.signature(module.grade)
        if "audit_data" in signature.parameters:
            result = module.grade(transcript, str(workspace_path), audit_data=audit_data)
        else:
            result = module.grade(transcript, str(workspace_path))
    except Exception as e:
        logger.error("grader.py failed for task %s: %s", task.task_id, e)
        return {}

    criteria = {}
    for name, c in result.get("criteria", {}).items():
        criteria[name] = CriterionResult(
            name=name,
            type=c.get("type", "weighted-sum"),
            value=float(c.get("value", 0)),
            weight=float(c.get("weight", 0)),
            details=c.get("details", ""),
        )

    return criteria


def _summarize_transcript(transcript: list[dict]) -> str:
    """Create a concise summary of the transcript for the LLM judge."""
    parts = []
    for record in transcript:
        rec_type = record.get("type", "")

        if rec_type == "message":
            msg = record.get("message", {})
            role = msg.get("role", "")
            content = msg.get("content", [])

            if isinstance(content, list):
                for item in content:
                    item_type = item.get("type", "")
                    if item_type == "text":
                        text = item.get("text", "")[:500]
                        parts.append(f"[{role}]: {text}")
                    elif item_type == "toolCall":
                        name = item.get("name", "")
                        args = json.dumps(item.get("arguments", {}), ensure_ascii=False)[:300]
                        parts.append(f"[{role} → tool:{name}]: {args}")
                    elif item_type == "toolResult":
                        tool_name = item.get("toolName", "")
                        result_text = item.get("result", "")
                        if isinstance(result_text, str):
                            result_text = result_text[:300]
                        else:
                            result_text = str(result_text)[:300]
                        parts.append(f"[tool:{tool_name} → {role}]: {result_text}")

        elif rec_type == "toolCall":
            name = record.get("name", "")
            args = json.dumps(record.get("arguments", {}), ensure_ascii=False)[:300]
            parts.append(f"[tool:{name}]: {args}")

    return "\n".join(parts[:100])  # Limit summary length


def grade_llm_judge(
    task: Task,
    transcript: list[dict],
    judge_base_url: str | None = None,
    judge_api_key: str | None = None,
    judge_model: str | None = None,
    judge_config: dict | None = None,
) -> dict[str, CriterionResult]:
    """Use an LLM judge to evaluate subjective criteria.

    Args:
        task: The Task object with judge_rubric.
        transcript: Parsed JSONL transcript.
        judge_base_url: OpenAI-compatible API base URL.
        judge_api_key: API key for the judge model.
        judge_model: Model ID for the judge.

    Returns:
        Dict of criterion name → CriterionResult.
    """
    if not task.has_judge or task.judge_rubric is None:
        logger.warning("No judge_rubric for task %s, skipping LLM judge", task.task_id)
        return {}

    rubric = task.judge_rubric

    # Resolve judge config from args, then rubric defaults, then env vars
    base_url = judge_base_url or rubric.api_base or os.environ.get("JUDGE_BASE_URL", "")
    api_key = judge_api_key or os.environ.get("JUDGE_API_KEY", "")
    model = judge_model or rubric.model or os.environ.get("JUDGE_MODEL_ID", JUDGE_DEFAULT_MODEL)

    if not base_url or not api_key:
        logger.error("Judge API not configured for task %s", task.task_id)
        return {}

    if not model:
        logger.error(
            "Judge model not configured for task %s. "
            "Set --judge-model, JUDGE_MODEL_ID env var, or model in judge_rubric.",
            task.task_id,
        )
        return {}

    # Build the judge prompt
    transcript_summary = _summarize_transcript(transcript)
    criteria_descriptions = []
    criterion_names = []
    for name, c in rubric.criteria.items():
        criterion_names.append(name)
        rubric_text = "\n".join(
            f"  - score {r.get('score', '?')}: {r.get('description', '')}"
            for r in c.rubric
        )
        criteria_descriptions.append(
            f"### {name} (weight: {c.weight})\n{c.description}\n\nRubric:\n{rubric_text}"
        )

    # Build the expected score keys hint for the judge
    score_keys_hint = ", ".join(f'"{n}": score' for n in criterion_names)

    prompt = (
        f"You are an expert evaluator for AI agent tasks. Evaluate the following agent execution.\n\n"
        f"## Task\nName: {task.name}\nCategory: {task.category}\n\n"
        f"## Task Prompt\n{task.prompt}\n\n"
        f"## Agent Transcript Summary\n{transcript_summary}\n\n"
        f"## Evaluation Criteria\n{'---'.join(criteria_descriptions)}\n\n"
        f"Respond with a JSON object:\n"
        f'{{"scores": {{{score_keys_hint}}}, "total": overall_score, "notes": "explanation"}}\n'
        f"Where each score is between 0.0 and 1.0."
    )

    # Call the judge API
    headers = {
        "Authorization": f"Bearer {api_key}",
        "Content-Type": "application/json",
    }
    request_cfg = dict(judge_config or {})
    request_cfg["model_id"] = model
    payload = build_chat_completion_request(
        request_cfg,
        messages=[
            {"role": "system", "content": "You are an expert evaluator. Respond only with valid JSON."},
            {"role": "user", "content": prompt},
        ],
    )

    url = f"{base_url.rstrip('/')}/chat/completions"

    for attempt in range(JUDGE_MAX_RETRIES):
        try:
            with httpx.Client(timeout=60.0) as client:
                resp = client.post(url, headers=headers, json=payload)
                resp.raise_for_status()
                data = resp.json()

            choice = data["choices"][0]
            message = choice.get("message", {})
            content = message.get("content") or ""
            if not content:
                reasoning_content = message.get("reasoning_content") or ""
                logger.warning(
                    "Judge response is empty (attempt %d, finish_reason=%s, reasoning_content_len=%d)",
                    attempt + 1,
                    choice.get("finish_reason", ""),
                    len(reasoning_content),
                )
                continue

            # Parse the JSON response (handle markdown code fences)
            content = re.sub(r"```json\s*", "", content)
            content = re.sub(r"```\s*", "", content)
            content = content.strip()

            # Try to extract JSON from the response
            json_match = re.search(r"\{.*\}", content, re.DOTALL)
            if json_match:
                judge_result = json.loads(json_match.group())
            else:
                logger.warning("Judge response is not valid JSON (attempt %d): %s", attempt + 1, content[:200])
                continue

            criterion_names = list(rubric.criteria.keys())
            scores = _extract_scores_payload(judge_result, criterion_names)

            criteria = {}
            for name, c in rubric.criteria.items():
                score, details = _extract_judge_score(
                    judge_result,
                    scores,
                    name,
                    str(judge_result.get("notes", "")),
                )
                criteria[name] = CriterionResult(
                    name=name,
                    type="weighted-sum",
                    value=score,
                    weight=c.weight,
                    details=details,
                )

            return criteria

        except Exception as e:
            logger.warning("Judge API call failed (attempt %d): %s", attempt + 1, e)
            continue

    logger.error("All judge API attempts failed for task %s", task.task_id)
    return {}


def grade_llm_judge_multi(
    task: Task,
    transcript: list[dict],
    judge_models_config: str | None = None,
) -> tuple[dict[str, CriterionResult], list[dict]]:
    """Use judge_models_config.yaml providers to evaluate subjective criteria."""
    judge_models = resolve_judge_models(judge_models_config)
    if not judge_models:
        logger.warning("No judge models available for task %s, skipping LLM judge", task.task_id)
        return {}, []

    def call_single(model_cfg: dict, _run_idx: int) -> dict:
        single_result = grade_llm_judge(
            task,
            transcript,
            judge_base_url=model_cfg["base_url"],
            judge_api_key=model_cfg["api_key"],
            judge_model=model_cfg["model_id"],
            judge_config=model_cfg,
        )
        return {
            name: {
                "type": criterion.type,
                "value": criterion.value,
                "weight": criterion.weight,
                "details": criterion.details,
            }
            for name, criterion in single_result.items()
        }

    criteria_dict, judge_models_used = run_multi_judge(judge_models, call_single)
    criteria = {
        name: CriterionResult(
            name=name,
            type=c.get("type", "weighted-sum"),
            value=float(c.get("value", 0.0)),
            weight=float(c.get("weight", 0.0)),
            details=c.get("details", ""),
            per_model=c.get("per_model", {}),
        )
        for name, c in criteria_dict.items()
    }
    return criteria, judge_models_used


def grade_task(
    task: Task,
    transcript: list[dict] | None,
    workspace_path: Path,
    run_id: str = "",
    grading_type: str = "auto",
    judge_base_url: str | None = None,
    judge_api_key: str | None = None,
    judge_model: str | None = None,
    judge_models_config: str | None = None,
    simple_scoring: bool = False,
    audit_data: dict | None = None,
) -> GradingResult:
    """Grade a task execution using the specified grading type.

    Args:
        task: The Task object.
        transcript: Parsed JSONL transcript (may be None on execution failure).
        workspace_path: Path to the workspace snapshot.
        run_id: Unique run identifier.
        grading_type: One of "auto", "llm_judge".
        judge_base_url: Judge API base URL.
        judge_api_key: Judge API key.
        judge_model: Judge model ID.
        simple_scoring: Deprecated no-op kept for caller compatibility.

    Returns:
        GradingResult with scores.
    """
    import time as _time
    start = _time.time()

    if grading_type not in {"auto", "llm_judge"}:
        raise ValueError(f"Unsupported grading_type: {grading_type}")

    result = GradingResult(
        task_id=task.task_id,
        run_id=run_id,
        task_version=task.version,
        grading_type=grading_type,
    )

    if transcript is None:
        result.error = "No transcript available"
        result.elapsed_seconds = _time.time() - start
        return result

    core_result = evaluate_task_trajectory(
        task_dir=task.task_dir,
        transcript=transcript,
        workspace_path=workspace_path,
        skip_judge=(grading_type == "auto"),
        judge_models_config=judge_models_config or (default_judge_models_config_path() if grading_type == "llm_judge" else None),
        judge_base_url=judge_base_url,
        judge_api_key=judge_api_key,
        judge_model=judge_model,
        audit_data=audit_data,
    )

    result.criteria = {
        name: CriterionResult(
            name=name,
            type=c.get("type", "weighted-sum"),
            value=float(c.get("value", 0.0)),
            weight=float(c.get("weight", 0.0)),
            details=c.get("details", ""),
            per_model=c.get("per_model", {}),
        )
        for name, c in core_result.get("criteria", {}).items()
    }
    result.total_score = float(core_result.get("total_score", 0.0))
    result.details = str(core_result.get("details", ""))
    result.judge_models_used = core_result.get("judge_models_used", [])
    result.aggregation_strategy = core_result.get("aggregation_strategy", "")
    result.elapsed_seconds = _time.time() - start

    return result


def save_grading_result(result: GradingResult, output_dir: Path) -> Path:
    """Save grading result to a JSON file.

    Args:
        result: The GradingResult to save.
        output_dir: Directory to save the result file.

    Returns:
        Path to the saved file.
    """
    output_dir.mkdir(parents=True, exist_ok=True)
    output_path = output_dir / "grading.json"

    data = {
        "task_id": result.task_id,
        "run_id": result.run_id,
        "task_version": result.task_version,
        "grading_type": result.grading_type,
        "total_score": result.total_score,
        "criteria": {
            name: {
                "type": c.type,
                "value": c.value,
                "weight": c.weight,
                "details": c.details,
                **({"per_model": c.per_model} if c.per_model else {}),
            }
            for name, c in result.criteria.items()
        },
        "details": result.details,
        "error": result.error,
        "elapsed_seconds": result.elapsed_seconds,
        "round_scores": result.round_scores,
        "stop_reason": result.stop_reason,
        **({"judge_models_used": result.judge_models_used} if result.judge_models_used else {}),
        **({"aggregation_strategy": result.aggregation_strategy} if result.aggregation_strategy else {}),
    }

    with open(output_path, "w", encoding="utf-8") as f:
        json.dump(data, f, indent=2, ensure_ascii=False)

    return output_path


def load_grading_result(path: Path) -> GradingResult | None:
    """Load a grading result from a JSON file."""
    if not path.exists():
        return None

    with open(path, encoding="utf-8") as f:
        data = json.load(f)

    criteria = {}
    for name, c in data.get("criteria", {}).items():
        criteria[name] = CriterionResult(
            name=name,
            type=c.get("type", "weighted-sum"),
            value=c.get("value", 0.0),
            weight=c.get("weight", 0.0),
            details=c.get("details", ""),
            per_model=c.get("per_model", {}),
        )

    return GradingResult(
        task_id=data.get("task_id", ""),
        run_id=data.get("run_id", ""),
        task_version=data.get("task_version", ""),
        criteria=criteria,
        total_score=data.get("total_score", 0.0),
        grading_type=data.get("grading_type", "automated"),
        details=data.get("details", ""),
        error=data.get("error"),
        elapsed_seconds=data.get("elapsed_seconds", 0.0),
        round_scores=data.get("round_scores", []),
        stop_reason=data.get("stop_reason", ""),
        judge_models_used=data.get("judge_models_used", []),
        aggregation_strategy=data.get("aggregation_strategy", ""),
    )
