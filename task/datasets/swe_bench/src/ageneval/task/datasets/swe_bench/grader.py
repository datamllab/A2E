"""Grade a SWE-bench instance inside the live sandbox.

``score_swe_bench(task, sandbox, model_patch)`` is called by
``SandboxScoringRunner`` while the container is still alive, using official
``swebench`` grading:
    1. fetch the test spec (``eval_script`` + gold tests) via the isolated
       ``_grade_helper`` (so ``swebench`` never enters the main env);
    2. run ``eval_script`` inside the sandbox on the agent-edited working tree
       (the agent already modified /testbed in place, so its fix is present);
    3. parse the captured log with the official log parser → resolved.

The agent's edits are graded as the working tree (which naturally includes any
new files it created), matching official "resolved" semantics for the source.
"""

from __future__ import annotations

import json
import logging
import os
import subprocess
import sys
import tempfile
from pathlib import Path
from typing import Any, Mapping

from ageneval.task.core.dataset import TaskInput

logger = logging.getLogger(__name__)

_HELPER = str(Path(__file__).with_name("_grade_helper.py"))
_EVAL_TIMEOUT = 1800  # seconds inside the container


def score_swe_bench(task: TaskInput, sandbox, model_patch: str) -> dict[str, Any]:
    """Grade the agent's changes. Returns at least ``{"resolved": bool}``."""
    inst = dict(task.metadata.get("swebench_instance", {}))
    if not inst:
        return {"resolved": False, "status": "no_instance"}

    return _grade_real(inst, sandbox)


def _grade_real(instance: Mapping[str, Any], sandbox) -> dict[str, Any]:
    try:
        spec = _helper_call("spec", instance)
    except Exception as exc:  # noqa: BLE001
        logger.exception("swebench spec fetch failed")
        return {"resolved": False, "status": "spec_error", "error": str(exc)[:500]}

    eval_script = spec.get("eval_script", "")
    if not eval_script:
        return {"resolved": False, "status": "no_eval_script"}

    # Run the official eval script on the agent-edited working tree.
    sandbox.write_file("/tmp/a2e_eval.sh", eval_script)
    res = sandbox.exec(
        ["bash", "-lc", "chmod +x /tmp/a2e_eval.sh && /tmp/a2e_eval.sh"],
        timeout=_EVAL_TIMEOUT,
    )
    log = (res.stdout or "") + "\n" + (res.stderr or "")

    # Parse the log with the official parser (isolated swebench).
    with tempfile.NamedTemporaryFile("w", suffix=".log", delete=False) as fh:
        fh.write(log)
        log_path = fh.name
    try:
        parsed = _helper_call("parse", instance, extra_args=[log_path])
    except Exception as exc:  # noqa: BLE001
        logger.exception("swebench log parse failed")
        return {"resolved": False, "status": "parse_error", "error": str(exc)[:500],
                "eval_log_tail": log[-2000:]}
    finally:
        os.unlink(log_path)

    parsed["eval_log_tail"] = log[-2000:]
    return parsed


def _helper_call(mode: str, instance: Mapping[str, Any], extra_args: list[str] | None = None) -> dict[str, Any]:
    """Invoke the self-contained swebench helper.

    Fast path: ``swebench`` already importable in this interpreter → run the
    helper module in-process. Isolated path: spawn ``uv run --with swebench``
    so the heavy dependency never has to coexist with the main lock.
    """
    payload = json.dumps(_jsonable(instance))
    if _swebench_importable():
        return _run_helper_inproc(mode, payload, extra_args or [])
    return _run_helper_subprocess(mode, payload, extra_args or [])


def _swebench_importable() -> bool:
    try:
        import swebench  # noqa: F401
        return True
    except Exception:  # noqa: BLE001
        return False


def _run_helper_inproc(mode: str, payload: str, extra_args: list[str]) -> dict[str, Any]:
    cmd = [sys.executable, _HELPER, mode, *extra_args]
    proc = subprocess.run(cmd, input=payload, capture_output=True, text=True, timeout=600)
    return _parse_helper_output(proc)


def _run_helper_subprocess(mode: str, payload: str, extra_args: list[str]) -> dict[str, Any]:
    cmd = [
        "uv", "run", "--no-project", "--index-strategy", "unsafe-best-match",
        "--with", "swebench", "python", _HELPER, mode, *extra_args,
    ]
    env = {**os.environ, "UV_HTTP_TIMEOUT": os.environ.get("UV_HTTP_TIMEOUT", "600")}
    proc = subprocess.run(
        cmd, input=payload, capture_output=True, text=True, timeout=1800, env=env
    )
    return _parse_helper_output(proc)


def _parse_helper_output(proc: subprocess.CompletedProcess) -> dict[str, Any]:
    if proc.returncode != 0:
        raise RuntimeError(f"swebench helper failed ({proc.returncode}): {proc.stderr[-800:]}")
    # The helper prints one JSON line last; tolerate leading uv/log noise.
    for line in reversed(proc.stdout.strip().splitlines()):
        line = line.strip()
        if line.startswith("{"):
            return json.loads(line)
    raise RuntimeError(f"swebench helper produced no JSON: {proc.stdout[-800:]}")


def _jsonable(obj: Any) -> Any:
    """Best-effort: HF rows can contain non-JSON scalars; coerce to JSON-safe."""
    try:
        json.dumps(obj)
        return obj
    except TypeError:
        if isinstance(obj, Mapping):
            return {k: _jsonable(v) for k, v in obj.items()}
        if isinstance(obj, (list, tuple)):
            return [_jsonable(v) for v in obj]
        return str(obj)
