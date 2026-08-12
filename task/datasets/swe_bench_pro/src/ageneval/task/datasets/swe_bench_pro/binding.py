"""SWE-bench Pro → generic-agent ``AgentBinding``.

Exposes two sandbox-backed tools (``bash`` + ``str_replace_editor``) whose
executor reaches the live sandbox through ``state["__sandbox__"]`` (injected by
``SandboxScoringRunner``), falling back to the ``sandbox()`` context accessor.
The agent edits the repository in place under ``/app``; the grader captures the
diff and re-applies it on a clean checkout before running the official tests, so
the agent need not emit a patch itself.

Shape mirrors the SWE-bench binding (each dataset owns its binding in A2E); the
only material difference is the ``/app`` working-directory wording.
"""

from __future__ import annotations

import logging
from collections.abc import Mapping, Sequence
from typing import Any

from ageneval.task.core import AgentBinding
from ageneval.task.datasets.swe_bench_pro.tools import get_tool_schemas

logger = logging.getLogger(__name__)

_MAX_OUT = 8000  # cap tool output fed back to the model (keep context small)


def build_swe_bench_pro_binding() -> AgentBinding:
    """Return everything a generic agent needs to solve a SWE-bench Pro instance."""
    return AgentBinding(
        name="swe-bench-pro",
        tool_schemas=get_tool_schemas(),
        tool_executor=_execute_tool,
        system_prompt_builder=_build_system_prompt,
    )


# ── sandbox access ──────────────────────────────────────────────────────────
def _get_sandbox(state: Mapping[str, Any]):
    sb = state.get("__sandbox__") if isinstance(state, Mapping) else None
    if sb is not None:
        return sb
    from ageneval.task.sandbox import sandbox

    return sandbox()


# ── tool executor ─────────────────────────────────────────────────────────────
def _execute_tool(name: str, arguments: Mapping[str, Any], state: Mapping[str, Any]) -> Any:
    sb = _get_sandbox(state)
    if name == "bash":
        cmd = str(arguments.get("command", "") or "")
        res = sb.exec(["bash", "-lc", cmd], timeout=300)
        return {
            "stdout": (res.stdout or "")[-_MAX_OUT:],
            "stderr": (res.stderr or "")[-4000:],
            "exit_code": res.returncode,
        }
    if name == "str_replace_editor":
        return _editor(sb, arguments)
    return {"error": f"unknown tool {name!r}"}


def _editor(sb, args: Mapping[str, Any]) -> dict[str, Any]:
    """Implement view / create / str_replace / insert via sandbox file ops."""
    cmd = str(args.get("command", ""))
    path = str(args.get("path", ""))
    if not path:
        return {"error": "path is required"}

    if cmd == "view":
        try:
            content = sb.read_file(path, text=True)
        except Exception as exc:
            return {"error": f"cannot read {path}: {exc}"}
        rng = args.get("view_range")
        lines = str(content).splitlines()
        if isinstance(rng, (list, tuple)) and len(rng) == 2:
            start, end = int(rng[0]), int(rng[1])
            lines = lines[max(0, start - 1):end]
            offset = max(1, start)
        else:
            offset = 1
        numbered = "\n".join(f"{i + offset}\t{ln}" for i, ln in enumerate(lines))
        return {"ok": True, "content": numbered[-_MAX_OUT:]}

    if cmd == "create":
        try:
            sb.write_file(path, str(args.get("file_text", "")))
            return {"ok": True, "created": path}
        except Exception as exc:
            return {"error": f"cannot create {path}: {exc}"}

    if cmd == "str_replace":
        old = str(args.get("old_str", ""))
        new = str(args.get("new_str", ""))
        try:
            content = str(sb.read_file(path, text=True))
        except Exception as exc:
            return {"error": f"cannot read {path}: {exc}"}
        count = content.count(old)
        if count == 0:
            return {"error": "old_str not found"}
        if count > 1:
            return {"error": f"old_str is not unique ({count} matches); add more context"}
        sb.write_file(path, content.replace(old, new, 1))
        return {"ok": True, "replaced_in": path}

    if cmd == "insert":
        line = int(args.get("insert_line", 0))
        new = str(args.get("new_str", ""))
        try:
            content = str(sb.read_file(path, text=True))
        except Exception as exc:
            return {"error": f"cannot read {path}: {exc}"}
        lines = content.splitlines()
        lines[line:line] = new.splitlines()
        sb.write_file(path, "\n".join(lines) + "\n")
        return {"ok": True, "inserted_in": path}

    return {"error": f"unknown editor command {cmd!r}"}


# ── system prompt ─────────────────────────────────────────────────────────────
def _build_system_prompt(tools: Sequence[Mapping[str, Any]]) -> str:
    tool_block = "\n".join(
        f"- {t['function']['name']}: {t['function'].get('description', '')}" for t in tools
    )
    return (
        "You are an expert software engineer fixing a real GitHub issue in a "
        "large professional codebase.\n"
        "You are working inside a sandboxed checkout of the repository whose "
        "root is /app, already set to the buggy commit. Explore with `bash`, "
        "then edit source files with `str_replace_editor` to resolve the issue "
        "described below.\n"
        "Do NOT edit test files — only fix the source. When you believe the fix "
        "is complete, stop; the system captures your changes automatically via "
        "`git diff` (you do not need to print a patch).\n"
        "Reply each turn with either a tool call or, if a binding prescribes a "
        'JSON protocol, {"action": "<tool>", "arguments": {...}} / '
        '{"final_answer": "<short summary>"}.\n\n'
        f"AVAILABLE TOOLS:\n{tool_block}\n"
    )
