"""Terminal-Bench 2.0 → generic-agent ``AgentBinding``.

The binding exposes two sandbox-backed tools (``bash`` + ``str_replace_editor``)
whose executor reaches the live container through ``state["__sandbox__"]``
(injected by ``SandboxScoringRunner``), falling back to the ``sandbox()`` context
accessor. The agent works directly inside the task's container; the dataset's
``score`` hook later copies the held-out tests in and runs the official verifier.
"""

from __future__ import annotations

import logging
from typing import Any, Mapping, Sequence

from ageneval.task.core import AgentBinding

from ageneval.task.datasets.terminal_bench_2.tools import get_tool_schemas

logger = logging.getLogger(__name__)

_MAX_OUT = 8000  # cap tool stdout fed back to the model (keep context small)


def build_terminal_bench_2_binding() -> AgentBinding:
    """Return everything a generic agent needs to solve a Terminal-Bench 2 task."""
    return AgentBinding(
        name="terminal-bench-2",
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
        except Exception as exc:  # noqa: BLE001
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
        except Exception as exc:  # noqa: BLE001
            return {"error": f"cannot create {path}: {exc}"}

    if cmd == "str_replace":
        old = str(args.get("old_str", ""))
        new = str(args.get("new_str", ""))
        try:
            content = str(sb.read_file(path, text=True))
        except Exception as exc:  # noqa: BLE001
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
        except Exception as exc:  # noqa: BLE001
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
        "You are an expert engineer operating a real Linux terminal inside a "
        "Docker container. Complete the task described below by running shell "
        "commands with the `bash` tool and editing files with "
        "`str_replace_editor`.\n"
        "Run `pwd` and `ls` first to orient yourself in the working directory. "
        "Any files you create or modify persist in the container and will be "
        "checked by a held-out test suite after you finish — so write your "
        "outputs to the exact paths the task specifies. Explore and act via tool "
        "calls; when you are confident the task is complete, stop.\n\n"
        f"AVAILABLE TOOLS:\n{tool_block}\n"
    )
