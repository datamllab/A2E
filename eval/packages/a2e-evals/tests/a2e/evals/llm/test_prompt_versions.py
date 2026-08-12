from typing import Any, Mapping

import pytest

from a2e.evals.exceptions import A2ETemplateMappingError
from a2e.evals.llm import PromptTemplate, TemplateFormat, a2e_prompt_to_prompt_template


def _chat_prompt_version_data() -> dict[str, Any]:
    return {
        "template_type": "CHAT",
        "template_format": "MUSTACHE",
        "template": {
            "type": "chat",
            "messages": [
                {"role": "system", "content": "Classify sentiment for {{text}}."},
                {"role": "user", "content": "{{text}}"},
            ],
        },
    }


class _PromptVersionStub:
    def __init__(self, payload: Mapping[str, Any]):
        self._payload = payload

    def _dumps(self) -> Mapping[str, Any]:
        return self._payload


def test_a2e_prompt_to_prompt_template_accepts_mapping() -> None:
    template = a2e_prompt_to_prompt_template(_chat_prompt_version_data())

    assert isinstance(template, PromptTemplate)
    assert template.template_format == TemplateFormat.MUSTACHE
    assert template.template == _chat_prompt_version_data()["template"]["messages"]

    rendered = template.render({"text": "this product is great"})
    assert rendered[0]["content"] == "Classify sentiment for this product is great."
    assert rendered[1]["content"] == "this product is great"


def test_a2e_prompt_to_prompt_template_accepts_prompt_version_object() -> None:
    payload = {
        "template_type": "STR",
        "template_format": "F_STRING",
        "template": {"type": "string", "template": "Rate this response: {response}"},
    }
    template = a2e_prompt_to_prompt_template(_PromptVersionStub(payload))

    assert isinstance(template, PromptTemplate)
    assert template.template_format == TemplateFormat.F_STRING
    rendered = template.render({"response": "Looks good"})
    assert rendered == [{"role": "user", "content": "Rate this response: Looks good"}]


def test_a2e_prompt_to_prompt_template_handles_none_template_format() -> None:
    payload = {
        "template_type": "STR",
        "template_format": "NONE",
        "template": {"type": "string", "template": "Classify this: {text}"},
    }
    template = a2e_prompt_to_prompt_template(payload)

    assert template.template_format is None
    rendered = template.render({"text": "hello"})
    assert rendered == [{"role": "user", "content": "Classify this: hello"}]


def test_a2e_prompt_to_prompt_template_normalizes_supported_roles() -> None:
    payload = {
        "template_type": "CHAT",
        "template_format": "MUSTACHE",
        "template": {
            "type": "chat",
            "messages": [
                {"role": "Developer", "content": "Be strict."},
                {"role": "Model", "content": "Previous answer."},
                {"role": "AI", "content": "Current answer."},
            ],
        },
    }
    template = a2e_prompt_to_prompt_template(payload)

    assert template.template == [
        {"role": "system", "content": "Be strict."},
        {"role": "assistant", "content": "Previous answer."},
        {"role": "assistant", "content": "Current answer."},
    ]


def test_a2e_prompt_to_prompt_template_raises_for_unsupported_role() -> None:
    payload = {
        "template_type": "CHAT",
        "template_format": "MUSTACHE",
        "template": {
            "type": "chat",
            "messages": [{"role": "tool", "content": "result"}],
        },
    }

    with pytest.raises(A2ETemplateMappingError, match="Unsupported message role"):
        a2e_prompt_to_prompt_template(payload)


def test_a2e_prompt_to_prompt_template_raises_for_unsupported_content_part_type() -> None:
    payload = {
        "template_type": "CHAT",
        "template_format": "MUSTACHE",
        "template": {
            "type": "chat",
            "messages": [
                {
                    "role": "user",
                    "content": [{"type": "tool_call", "tool_call_id": "x", "tool_call": {}}],
                }
            ],
        },
    }

    with pytest.raises(A2ETemplateMappingError, match="Only 'text' is supported"):
        a2e_prompt_to_prompt_template(payload)


def test_a2e_prompt_to_prompt_template_raises_for_string_messages_payload() -> None:
    payload = {
        "template_type": "CHAT",
        "template_format": "MUSTACHE",
        "template": {
            "type": "chat",
            "messages": "not-a-message-list",
        },
    }

    with pytest.raises(A2ETemplateMappingError, match="sequence 'messages' field"):
        a2e_prompt_to_prompt_template(payload)
