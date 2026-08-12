"""Execution-based HumanEval scoring (pass@1).

The standard HumanEval metric runs the model's completion together with the
problem's hidden unit tests and checks that they pass — substring matching
against the canonical solution is meaningless for code generation (a correct
program written differently scores 0). This module builds the full program
``prompt + completion + test + check(entry_point)`` and executes it in an
isolated subprocess with a wall-clock timeout.

Self-contained: depends only on the stdlib. The completion is whatever the agent
returned as ``final_answer`` (the function body, or occasionally a full function
redefinition — both are handled).
"""

from __future__ import annotations

import json
import logging
import subprocess
import sys
import tempfile
from pathlib import Path

logger = logging.getLogger(__name__)

_DEFAULT_TIMEOUT = 15


def _clean_completion(completion: str) -> str:
    """Strip markdown fences / a leading ``{"final_answer": ...}`` wrapper.

    The binding asks the model for a bare function body, but defensively recover
    the code when a model wraps it in a JSON object or a ```python fence.
    """
    text = completion or ""
    if not text.strip():
        return ""
    # Unwrap a JSON {"final_answer": "..."} envelope if the model emitted one.
    stripped = text.lstrip()
    if stripped.startswith("{") and "final_answer" in stripped:
        try:
            obj = json.loads(stripped)
            if isinstance(obj, dict) and "final_answer" in obj:
                text = str(obj["final_answer"])
        except (ValueError, TypeError):
            pass
    # Strip a ```python ... ``` fence without dropping function-body indent.
    if text.lstrip().startswith("```"):
        lines = text.splitlines()
        if lines and lines[0].lstrip().startswith("```"):
            lines = lines[1:]
        if lines and lines[-1].strip().startswith("```"):
            lines = lines[:-1]
        text = "\n".join(lines)
    lines = text.splitlines()
    while lines and not lines[0].strip():
        lines.pop(0)
    while lines and not lines[-1].strip():
        lines.pop()
    return "\n".join(lines)


def build_program(prompt: str, completion: str, test_src: str, entry_point: str) -> str:
    """Assemble the full runnable program for a HumanEval problem."""
    body = _clean_completion(completion)
    if f"def {entry_point}" in body:
        # Model redefined the whole function. Keep imports from the prompt.
        import_lines = "\n".join(
            ln for ln in prompt.splitlines()
            if ln.startswith(("import ", "from "))
        )
        head = f"{import_lines}\n" if import_lines else ""
        program = f"{head}{body}\n\n{test_src}\n\ncheck({entry_point})\n"
    else:
        # Model returned just the body — continues the prompt's signature.
        program = f"{prompt}{body}\n\n{test_src}\n\ncheck({entry_point})\n"
    return program


def run_humaneval_pass(
    prompt: str,
    completion: str,
    test_src: str,
    entry_point: str,
    *,
    timeout: int = _DEFAULT_TIMEOUT,
) -> dict:
    """Run pass@1 for one problem; return ``{"passed", "error"}``.

    Executes in a fresh subprocess so a model infinite-loop or crash cannot take
    down the harness. ``passed`` is True iff the program (asserts included) exits 0.
    """
    program = build_program(prompt, completion, test_src, entry_point)
    if not _clean_completion(completion):
        return {"passed": False, "error": "empty completion"}
    with tempfile.TemporaryDirectory() as td:
        path = Path(td) / "candidate.py"
        path.write_text(program, encoding="utf-8")
        try:
            proc = subprocess.run(
                [sys.executable, str(path)],
                capture_output=True,
                text=True,
                timeout=timeout,
                cwd=td,
            )
        except subprocess.TimeoutExpired:
            return {"passed": False, "error": f"timeout>{timeout}s"}
        except Exception as exc:
            return {"passed": False, "error": f"{type(exc).__name__}: {exc}"[:300]}
    if proc.returncode == 0:
        return {"passed": True, "error": None}
    return {"passed": False, "error": (proc.stderr or proc.stdout or "non-zero exit")[-300:]}


def score_humaneval_state(final_answer: str, initial_state: dict, *, timeout: int = _DEFAULT_TIMEOUT) -> dict:
    """Convenience wrapper: read prompt/test/entry_point from ``initial_state``."""
    return run_humaneval_pass(
        prompt=str(initial_state.get("prompt", "")),
        completion=final_answer or "",
        test_src=str(initial_state.get("test", "")),
        entry_point=str(initial_state.get("entry_point", "")),
        timeout=timeout,
    )
