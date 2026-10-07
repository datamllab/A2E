"""Jev (System One) client for the extra judge dimension.

The original LLM metrics stay on the chat LLM. This module is only used by
the ``*_jev`` scores.
"""

from __future__ import annotations

import json
import os
import time
import urllib.error
import urllib.request
from collections.abc import Mapping, Sequence
from typing import Any

DEFAULT_JEV_URL = "https://openrouter.ai/api/v1/systemone"
DEFAULT_JEV_MODEL = "jev-latest"
_RETRYABLE = {408, 409, 429, 500, 502, 503, 504, 520, 524}


def prompt_to_text(prompt: Any) -> str:
    if prompt is None:
        return ""
    if isinstance(prompt, str):
        return prompt
    if isinstance(prompt, list):
        parts: list[str] = []
        for message in prompt:
            if isinstance(message, Mapping):
                content = message.get("content", "")
                if isinstance(content, list):
                    content = " ".join(
                        part.get("text", "") if isinstance(part, Mapping) else str(part)
                        for part in content
                    )
                role = message.get("role", "")
                if hasattr(role, "value"):
                    role = role.value
                parts.append(f"{role}: {content}".strip(": "))
            else:
                parts.append(str(message))
        return "\n\n".join(part for part in parts if part)
    return str(prompt)


def criteria_from_labels(labels: Sequence[str] | Mapping[str, Any]) -> dict[str, str]:
    if isinstance(labels, Mapping):
        return {str(key): str(value) for key, value in labels.items()}
    return {str(label): f"Select {label}." for label in labels}


def resolve_jev_url(base_url: str | None = None) -> str:
    raw = (base_url or os.getenv("A2E_JEV_URL") or DEFAULT_JEV_URL).strip()
    url = raw.rstrip("/")
    if url.endswith("/systemone"):
        return url
    if "openrouter.ai" in url:
        return f"{url}/systemone"
    return url or DEFAULT_JEV_URL


def resolve_jev_api_key(api_key: str | None = None) -> str:
    return (
        api_key
        or os.getenv("OPENROUTER_API_KEY")
        or os.getenv("A2E_JEV_API_KEY")
        or os.getenv("A2E_EVAL_LLM_API_KEY")
        or os.getenv("OPENAI_API_KEY")
        or ""
    )


def call_systemone(
    *,
    state: str,
    questions: Mapping[str, Any],
    model: str = DEFAULT_JEV_MODEL,
    api_key: str | None = None,
    base_url: str | None = None,
    timeout: float = 90.0,
    attempts: int = 6,
) -> dict[str, Any]:
    key = resolve_jev_api_key(api_key)
    if not key:
        raise RuntimeError("Jev API key missing (set OPENROUTER_API_KEY or A2E_JEV_API_KEY)")
    body = json.dumps(
        {"model": model, "state": state, "questions": dict(questions)},
        ensure_ascii=False,
    ).encode()
    url = resolve_jev_url(base_url)
    last_error = "jev request failed"
    for attempt in range(attempts):
        request = urllib.request.Request(
            url,
            data=body,
            headers={
                "Authorization": f"Bearer {key}",
                "Content-Type": "application/json",
            },
        )
        try:
            with urllib.request.urlopen(request, timeout=timeout) as response:
                payload = json.load(response)
            if not isinstance(payload, dict):
                raise RuntimeError("jev returned a non-object payload")
            return payload
        except urllib.error.HTTPError as exc:
            last_error = exc.read().decode(errors="replace")[:300]
            if exc.code not in _RETRYABLE:
                raise RuntimeError(f"HTTP {exc.code}: {last_error}") from exc
            time.sleep(min(30, 2**attempt))
        except Exception as exc:
            last_error = str(exc)
            time.sleep(min(30, 2**attempt))
    raise RuntimeError(last_error)


def uses_jev(llm: Any) -> bool:
    if llm is None:
        return False
    if bool(getattr(llm, "uses_jev", False)):
        return True
    provider = str(getattr(llm, "provider", "") or "").lower()
    return provider in {"jev", "systemone", "system-one"}


class JevLLM:
    """Duck-typed judge client used in place of `a2e.evals.llm.LLM`."""

    uses_jev = True
    provider = "jev"

    def __init__(
        self,
        *,
        model: str | None = None,
        api_key: str | None = None,
        base_url: str | None = None,
        timeout: float = 90.0,
    ) -> None:
        self.model = model or os.getenv("A2E_EVAL_LLM_MODEL") or DEFAULT_JEV_MODEL
        self.api_key = resolve_jev_api_key(api_key)
        self.base_url = resolve_jev_url(base_url)
        self.timeout = timeout
        self.last_confidence: float | None = None
        self.last_cost: float | None = None
        self.last_raw: dict[str, Any] | None = None

    def generate_classification(
        self,
        prompt: Any,
        labels: Sequence[str] | Mapping[str, Any],
        include_explanation: bool = True,
        description: str | None = None,
        **kwargs: Any,
    ) -> dict[str, Any]:
        del include_explanation, kwargs
        state = prompt_to_text(prompt)
        if description:
            state = f"{description.strip()}\n\n{state}"
        payload = call_systemone(
            state=state,
            questions={
                "label": {
                    "type": "choice",
                    "instructions": (
                        "Choose exactly one label that best matches the evaluation rubric. "
                        "Ignore presentation order and answer length."
                    ),
                    "criteria": criteria_from_labels(labels),
                }
            },
            model=self.model,
            api_key=self.api_key,
            base_url=self.base_url,
            timeout=self.timeout,
        )
        answer = ((payload.get("answers") or {}).get("label") or {})
        label = str(answer.get("choice") or "").strip()
        confidence = answer.get("confidence")
        try:
            self.last_confidence = float(confidence) if confidence is not None else None
        except (TypeError, ValueError):
            self.last_confidence = None
        usage = payload.get("usage") or {}
        try:
            self.last_cost = float(usage.get("cost")) if usage.get("cost") is not None else None
        except (TypeError, ValueError):
            self.last_cost = None
        self.last_raw = payload
        explanation = "jev"
        if self.last_confidence is not None:
            explanation = f"jev confidence={self.last_confidence:.3f}"
        return {"label": label, "explanation": explanation}

    async def async_generate_classification(
        self,
        prompt: Any,
        labels: Sequence[str] | Mapping[str, Any],
        include_explanation: bool = True,
        description: str | None = None,
        **kwargs: Any,
    ) -> dict[str, Any]:
        return self.generate_classification(
            prompt,
            labels,
            include_explanation=include_explanation,
            description=description,
            **kwargs,
        )

    def generate_text(self, prompt: Any = "", **kwargs: Any) -> str:
        del kwargs
        raise RuntimeError("Jev does not generate free-form judge text; use generate_classification")
