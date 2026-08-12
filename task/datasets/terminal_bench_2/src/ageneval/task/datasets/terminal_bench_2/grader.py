"""Grade a Terminal-Bench 2.0 task inside the live sandbox.

``score_terminal_bench_2(task, sandbox, model_patch)`` is called by
``SandboxScoringRunner`` while the container is still alive, reproducing the
official TB2 verifier flow:

    1. copy the held-out ``tests/`` dir into the container at ``/tests/`` (the
       agent never saw these — they arrive only at grading time);
    2. ``mkdir -p /logs/verifier`` (where TB2's ``test.sh`` writes its outputs);
    3. run ``bash /tests/test.sh`` in the task working dir. The script bootstraps
       pytest, runs ``test_outputs.py`` against the agent-modified container, and
       writes ``1``/``0`` to ``/logs/verifier/reward.txt``;
    4. read ``reward.txt`` → ``resolved``; parse ``ctrf.json`` for test counts.

``test.sh`` installs uv/pytest from the internet. If the host only reaches the
internet through a proxy, set ``A2E_TB2_SCORE_PROXY`` (or rely on the host
``http_proxy`` being rewritten to the docker bridge gateway) so the container can
fetch them; otherwise scoring degrades gracefully to ``resolved=False`` while the
agent trajectory is still fully captured.
"""

from __future__ import annotations

import json
import logging
import os
from pathlib import Path
from typing import Any

from ageneval.task.core.dataset import TaskInput

logger = logging.getLogger(__name__)

_DEFAULT_DOCKER_GW = "172.17.0.1"  # default docker bridge gateway (host from container)


def _tests_dir_for(task: TaskInput) -> Path:
    """Resolve the vendored ``tests/`` dir for this task (package data)."""
    name = str(task.metadata.get("tb_task") or task.task_id)
    return Path(__file__).resolve().parent / "vendor" / "tasks" / name / "tests"


def _container_proxy_env() -> dict[str, str]:
    """Proxy env to inject so the in-container verifier can reach the internet.

    Priority: explicit ``A2E_TB2_SCORE_PROXY`` → host proxy with
    localhost/127.0.0.1 rewritten to the docker bridge gateway → none.
    """
    override = os.environ.get("A2E_TB2_SCORE_PROXY")
    host = override or os.environ.get("https_proxy") or os.environ.get("http_proxy") \
        or os.environ.get("HTTPS_PROXY") or os.environ.get("HTTP_PROXY")
    if not host:
        return {}
    gw = os.environ.get("A2E_TB2_DOCKER_GW", _DEFAULT_DOCKER_GW)
    fixed = host.replace("127.0.0.1", gw).replace("localhost", gw)
    return {
        "http_proxy": fixed, "https_proxy": fixed,
        "HTTP_PROXY": fixed, "HTTPS_PROXY": fixed,
    }


def _copy_tests_into_container(tests_dir: Path, sandbox) -> int:
    """Write every file under ``tests_dir`` to ``/tests/`` in the container."""
    count = 0
    for path in sorted(tests_dir.rglob("*")):
        if not path.is_file():
            continue
        rel = path.relative_to(tests_dir).as_posix()
        sandbox.write_file(f"/tests/{rel}", path.read_bytes())
        count += 1
    return count


def _parse_ctrf(sandbox) -> dict[str, Any]:
    """Best-effort parse of the CTRF json the verifier may emit. Returns counts."""
    try:
        raw = sandbox.read_file("/logs/verifier/ctrf.json", text=True)
        summary = (json.loads(raw).get("results") or {}).get("summary") or {}
        return {
            "tb_tests_total": summary.get("tests"),
            "tb_tests_passed": summary.get("passed"),
            "tb_tests_failed": summary.get("failed"),
        }
    except Exception:  # noqa: BLE001 - ctrf is optional / may be absent on hard failures
        return {}


def score_terminal_bench_2(task: TaskInput, sandbox, model_patch: str) -> dict[str, Any]:
    """Grade the agent's work via the official held-out tests. Returns at least
    ``{"resolved": bool}`` (plus reward + per-test counts when available)."""
    tests_dir = _tests_dir_for(task)
    if not (tests_dir / "test.sh").exists():
        return {"resolved": False, "status": "no_tests"}

    workdir = str(task.metadata.get("tb_workdir") or "/app")
    timeout = int(float(task.metadata.get("verifier_timeout_sec") or 900.0))

    try:
        n_files = _copy_tests_into_container(tests_dir, sandbox)
        sandbox.exec(["mkdir", "-p", "/logs/verifier"])
        res = sandbox.exec(
            ["bash", "/tests/test.sh"],
            cwd=workdir,
            env=_container_proxy_env() or None,
            timeout=timeout,
        )
    except Exception as exc:  # noqa: BLE001
        logger.exception("terminal-bench-2 verifier crashed on %s", task.task_id)
        return {"resolved": False, "status": "verifier_error", "score_error": str(exc)[:500]}

    reward_raw = ""
    try:
        reward_raw = str(sandbox.read_file("/logs/verifier/reward.txt", text=True)).strip()
    except Exception:  # noqa: BLE001 - reward file absent => verifier failed to run
        pass

    resolved = reward_raw == "1"
    report: dict[str, Any] = {
        "resolved": resolved,
        "tb_reward": reward_raw or None,
        "status": "graded" if reward_raw else "no_reward",
        "tb_verifier_files": n_files,
        "tb_verifier_exit": res.returncode,
    }
    if not reward_raw:
        # Surface a tail of stderr so a misconfigured verifier (e.g. no internet
        # to bootstrap pytest) is diagnosable from the trace.
        report["tb_verifier_stderr_tail"] = (res.stderr or "")[-800:]
    report.update(_parse_ctrf(sandbox))
    logger.info("terminal-bench-2 score %s: resolved=%s reward=%r",
                task.task_id, resolved, reward_raw)
    return report
