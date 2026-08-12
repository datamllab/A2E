"""Grade a SWE-bench Pro instance inside the live sandbox.

``score_swe_bench_pro(task, sandbox, model_patch)`` is called by
``SandboxScoringRunner`` while the container is still alive. It reproduces the
**official** ``scaleapi/SWE-bench_Pro-os`` evaluation exactly:

    1. capture the agent's change set as a patch (``git add -A`` + diff vs
       base_commit, so new files are included);
    2. build the official *entryscript* — reset /app to ``base_commit``, apply
       the model patch, run the instance's ``before_repo_set_cmd`` (last line),
       then the vendored per-instance ``run_script.sh`` over the selected test
       files, then the vendored per-instance ``parser.py`` -> ``output.json``;
    3. resolved := every test in (fail_to_pass + pass_to_pass) has status PASSED
       -- byte-for-byte the official criterion (``swe_bench_pro_eval.py:main``).

The per-instance ``run_script.sh`` / ``parser.py`` are the official MIT-licensed
scripts, vendored via ``harness.py`` (no out-of-repo dependency).
"""

from __future__ import annotations

import ast
import json
import logging
import re
from collections.abc import Mapping, Sequence
from typing import Any

from ageneval.task.core.dataset import TaskInput
from ageneval.task.datasets.swe_bench_pro.harness import get_instance_scripts

logger = logging.getLogger(__name__)

_EVAL_TIMEOUT = 1800  # seconds inside the container (official Modal timeout = 3600)
_EMPTY_COUNTS = {"f2p_passed": 0, "f2p_total": 0, "p2p_passed": 0, "p2p_total": 0}


# ── helpers ───────────────────────────────────────────────────────────────────
def _literal_list(value: Any) -> list[str]:
    """Parse a stored Python/JSON list literal into a list of strings.

    SWE-bench Pro stores ``fail_to_pass`` / ``pass_to_pass`` /
    ``selected_test_files_to_run`` as Python list reprs (single-quoted); the
    official harness parses them with ``eval(...)``. We use ``ast.literal_eval``
    (safe) and fall back to ``json.loads``.
    """
    if isinstance(value, (list, tuple)):
        return [str(v) for v in value]
    s = str(value or "").strip()
    if not s:
        return []
    for parser in (ast.literal_eval, json.loads):
        try:
            out = parser(s)
            if isinstance(out, (list, tuple)):
                return [str(v) for v in out]
        except (ValueError, SyntaxError, TypeError):
            continue
    return []


def _strip_binary_hunks(patch: str) -> str:
    """Remove binary diff sections from a git patch (official behaviour)."""
    if not patch:
        return patch
    sections = re.split(r"(?=^diff --git )", patch, flags=re.MULTILINE)
    kept: list[str] = []
    for section in sections:
        if not section.strip():
            continue
        if re.search(r"^Binary files .* differ$", section, re.MULTILINE):
            continue
        if re.search(r"^GIT binary patch$", section, re.MULTILINE):
            continue
        kept.append(section)
    return "".join(kept)


def _entryscript(base_commit: str, before_repo_set_last: str, test_files: Sequence[str]) -> str:
    """Build the official per-instance entryscript (see create_entryscript)."""
    files_arg = ",".join(test_files)
    return (
        "cd /app\n"
        f"git reset --hard {base_commit}\n"
        f"git checkout {base_commit}\n"
        "git apply -v /workspace/patch.diff\n"
        f"{before_repo_set_last}\n"
        f"bash /workspace/run_script.sh {files_arg} > /workspace/stdout.log 2> /workspace/stderr.log\n"
        "python /workspace/parser.py /workspace/stdout.log /workspace/stderr.log /workspace/output.json\n"
    )


def _capture_patch(sandbox, base_commit: str) -> str:
    """Capture the agent's full change set under /app as a git-apply-able patch.

    ``git add -A`` then ``git diff --cached <base_commit>`` includes new files
    and is taken relative to ``base_commit`` (the buggy state the agent edited
    on top of), so it re-applies cleanly after the grader resets to base_commit.
    """
    cmd = (
        "cd /app && git -c core.fileMode=false add -A >/dev/null 2>&1; "
        f"git -c core.fileMode=false diff --cached {base_commit}"
    )
    res = sandbox.exec(["bash", "-lc", cmd], timeout=180)
    return res.stdout or ""


def _log_tail(sandbox, n: int = 2500) -> str:
    """Best-effort tail of the in-container eval logs for debugging."""
    out = []
    for fn in ("/workspace/stdout.log", "/workspace/stderr.log"):
        try:
            out.append(f"--- {fn} ---\n{str(sandbox.read_file(fn, text=True))[-n:]}")
        except Exception:
            pass
    return "\n".join(out)


# ── core grading ────────────────────────────────────────────────────────────
def grade_with_patch(instance: Mapping[str, Any], sandbox, patch: str) -> dict[str, Any]:
    """Run the official eval for ``instance`` with a given ``patch`` (gold or model).

    Returns at least ``{"resolved": bool, "status": str, f2p/p2p counts}``.
    """
    instance_id = str(instance.get("instance_id", ""))
    base_commit = str(instance.get("base_commit", ""))
    f2p = set(_literal_list(instance.get("fail_to_pass")))
    p2p = set(_literal_list(instance.get("pass_to_pass")))
    counts = {
        "f2p_passed": 0, "f2p_total": len(f2p),
        "p2p_passed": 0, "p2p_total": len(p2p),
    }

    try:
        run_script, parser_py = get_instance_scripts(instance_id)
    except FileNotFoundError as exc:
        logger.error("no vendored harness scripts for %s", instance_id)
        return {"resolved": False, "status": "no_harness_scripts",
                "score_error": str(exc)[:300], **counts}

    test_files = _literal_list(instance.get("selected_test_files_to_run"))
    before_last = (str(instance.get("before_repo_set_cmd", "")).strip().split("\n") or [""])[-1]
    patch = _strip_binary_hunks(patch or "")

    # Stage the official workspace files, then run the entryscript.
    sandbox.write_file("/workspace/patch.diff", patch)
    sandbox.write_file("/workspace/run_script.sh", run_script)
    sandbox.write_file("/workspace/parser.py", parser_py)
    sandbox.write_file("/workspace/entryscript.sh", _entryscript(base_commit, before_last, test_files))
    sandbox.exec(["bash", "/workspace/entryscript.sh"], timeout=_EVAL_TIMEOUT)

    # Read the official parser output (tests[] with PASSED/FAILED/... statuses).
    try:
        output = json.loads(str(sandbox.read_file("/workspace/output.json", text=True)))
    except Exception as exc:
        logger.warning("SWE-bench Pro: no output.json for %s (%s)", instance_id, exc)
        return {"resolved": False, "status": "no_test_output",
                "score_error": str(exc)[:300], "eval_log_tail": _log_tail(sandbox), **counts}

    passed = {str(t.get("name")) for t in output.get("tests", []) if t.get("status") == "PASSED"}
    required = f2p | p2p
    resolved = bool(required) and required <= passed  # official: (f2p|p2p) subset of passed
    counts["f2p_passed"] = len(f2p & passed)
    counts["p2p_passed"] = len(p2p & passed)
    return {
        "resolved": resolved,
        "status": "resolved" if resolved else "unresolved",
        "tests_total": len(output.get("tests", [])),
        "tests_passed": len(passed),
        **counts,
        "model_patch": patch,
    }


def score_swe_bench_pro(task: TaskInput, sandbox, model_patch: str) -> dict[str, Any]:
    """SandboxScoringRunner score hook: grade the agent's in-place edits to /app."""
    inst = dict((task.metadata or {}).get("swebench_pro_instance", {}))
    if not inst:
        return {"resolved": False, "status": "no_instance", **_EMPTY_COUNTS}
    base_commit = str(inst.get("base_commit", ""))
    # Re-derive the full patch (incl. new files) from the sandbox; fall back to
    # the runner-provided ``git diff`` if for some reason capture came back empty.
    patch = _capture_patch(sandbox, base_commit)
    if not patch.strip() and model_patch:
        patch = model_patch
    return grade_with_patch(inst, sandbox, patch)


def setup_swe_bench_pro(task: TaskInput, sandbox) -> None:
    """SandboxScoringRunner setup hook: reset /app to base_commit before the agent.

    Guarantees the agent edits the *buggy* state (the image's default HEAD may
    differ), so its captured diff applies cleanly during grading.
    """
    base_commit = str((task.metadata or {}).get("swebench_pro_instance", {}).get("base_commit", ""))
    if not base_commit:
        return
    sandbox.exec(
        ["bash", "-lc", f"cd /app && git reset --hard {base_commit} && git checkout {base_commit}"],
        timeout=300,
    )
