"""Normalize agent transcripts before grading.

Task graders in this repository expect a canonical OpenClaw message-style
transcript. Some model backends emit OpenClaw trajectory events instead. This
module converts supported trajectory events into the canonical records without
requiring every generated grader to know each backend schema.
"""

from __future__ import annotations

from copy import deepcopy
from typing import Any


CANONICAL_TYPES = {"message", "toolCall", "toolResult"}


def normalize_transcript_for_grader(records: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """Return a canonical transcript suitable for task graders.

    The function is intentionally conservative: if the transcript already
    contains canonical records, it is returned unchanged. Otherwise, supported
    OpenClaw trajectory events such as prompt.submitted and model.completed are
    converted into message records.
    """
    if any(record.get("type") in CANONICAL_TYPES for record in records):
        return records

    normalized: list[dict[str, Any]] = []
    seen_user_prompts: set[str] = set()
    seen_assistant_texts: set[str] = set()

    for record in records:
        rec_type = record.get("type")
        data = record.get("data", {})
        if not isinstance(data, dict):
            data = {}

        if rec_type == "round_boundary":
            normalized.append(deepcopy(record))
            continue

        if rec_type == "prompt.submitted":
            prompt = _first_string(data.get("prompt"), data.get("userPrompt"))
            if prompt and prompt not in seen_user_prompts:
                normalized.append(_message_record("user", [_text_item(prompt)], record))
                seen_user_prompts.add(prompt)
            continue

        if rec_type != "model.completed":
            continue

        snapshot_records = _records_from_messages_snapshot(data.get("messagesSnapshot"), record)
        for item in snapshot_records:
            role = item.get("message", {}).get("role", "")
            if role == "user":
                text = _message_text(item)
                if text in seen_user_prompts:
                    continue
                if text:
                    seen_user_prompts.add(text)
            elif role == "assistant":
                text = _message_text(item)
                if text:
                    seen_assistant_texts.add(text)
            normalized.append(item)

        assistant_texts = data.get("assistantTexts")
        if isinstance(assistant_texts, list):
            for text in assistant_texts:
                if not isinstance(text, str) or not text or text in seen_assistant_texts:
                    continue
                normalized.append(_message_record("assistant", [_text_item(text)], record))
                seen_assistant_texts.add(text)

    return normalized if normalized else records


def _records_from_messages_snapshot(value: Any, source: dict[str, Any]) -> list[dict[str, Any]]:
    if not isinstance(value, list):
        return []

    records: list[dict[str, Any]] = []
    for message in value:
        if not isinstance(message, dict):
            continue
        role = str(message.get("role") or "")
        if not role:
            continue
        content = _normalize_content(message.get("content"))
        if not content:
            continue
        records.append(_message_record(role, content, source))
    return records


def _normalize_content(value: Any) -> list[dict[str, Any]]:
    if isinstance(value, str):
        return [_text_item(value)] if value else []
    if not isinstance(value, list):
        return []

    content: list[dict[str, Any]] = []
    for item in value:
        if isinstance(item, str):
            if item:
                content.append(_text_item(item))
            continue
        if not isinstance(item, dict):
            continue

        item_type = item.get("type")
        if item_type == "text":
            text = _first_string(item.get("text"), item.get("content"))
            if text:
                content.append(_text_item(text))
        elif item_type == "toolCall":
            content.append({
                "type": "toolCall",
                "id": item.get("id") or item.get("toolCallId") or item.get("callId"),
                "name": item.get("name") or item.get("toolName") or "",
                "arguments": item.get("arguments") or item.get("args") or {},
            })
        elif item_type == "toolResult":
            content.append({
                "type": "toolResult",
                "toolCallId": item.get("toolCallId") or item.get("id") or item.get("callId"),
                "toolName": item.get("toolName") or item.get("name") or "",
                "result": item.get("result") or item.get("content") or "",
            })
    return content


def _message_record(role: str, content: list[dict[str, Any]], source: dict[str, Any]) -> dict[str, Any]:
    record = {
        "type": "message",
        "message": {
            "role": role,
            "content": content,
        },
    }
    for key in ("_round", "round"):
        if key in source:
            record[key] = source[key]
    return record


def _text_item(text: str) -> dict[str, str]:
    return {"type": "text", "text": text}


def _first_string(*values: Any) -> str:
    for value in values:
        if isinstance(value, str) and value:
            return value
    return ""


def _message_text(record: dict[str, Any]) -> str:
    content = record.get("message", {}).get("content", [])
    if isinstance(content, str):
        return content
    if not isinstance(content, list):
        return ""
    texts = []
    for item in content:
        if isinstance(item, dict) and item.get("type") == "text" and item.get("text"):
            texts.append(str(item["text"]))
    return "\n".join(texts)
