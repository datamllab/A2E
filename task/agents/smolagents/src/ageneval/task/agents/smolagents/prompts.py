"""Optional additional-instruction builder for smolagents.

smolagents ships with its own elaborate code-agent system prompt, so we
only pass a short *additional_instructions* string derived from the
binding's domain-specific system prompt. Keep the binding's tool docs
out of here — smolagents builds them automatically from each
``Tool.description`` / ``Tool.inputs``.
"""

from __future__ import annotations


def build_additional_instructions(binding_prompt: str) -> str:
    """Trim the binding's system prompt down to the dataset-specific bits.

    The binding's full prompt typically appends an inline tool catalog (so
    that bare LLM agents can still use the tools without an MCP server).
    smolagents already exposes the tools natively, so the catalog would be
    duplicate noise. We keep the textual policy preamble and drop the
    "AVAILABLE TOOLS:" block.
    """
    if not binding_prompt:
        return ""
    marker = "AVAILABLE TOOLS:"
    head = binding_prompt.split(marker, 1)[0].strip()
    if not head:
        return binding_prompt.strip()
    return head
