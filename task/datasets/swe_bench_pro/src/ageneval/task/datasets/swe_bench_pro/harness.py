"""Locate the vendored official SWE-bench Pro grading scripts.

SWE-bench Pro has **no PyPI grading package**. The authoritative grader is the
per-instance ``run_script.sh`` (test runner) + ``parser.py`` (log → test status)
shipped in ``scaleapi/SWE-bench_Pro-os`` (MIT). We vendor those scripts as a
tarball (``_harness/run_scripts.tar.gz``) so A2E grades exactly like the official
harness while staying standalone (no out-of-repo path dependency).

On first use the tarball is extracted to a per-machine cache dir; afterwards the
per-instance scripts are read directly. ``grader.py`` feeds them to the sandbox.
"""

from __future__ import annotations

import logging
import tarfile
import tempfile
import threading
from pathlib import Path

logger = logging.getLogger(__name__)

_HARNESS_DIR = Path(__file__).with_name("_harness")
_TARBALL = _HARNESS_DIR / "run_scripts.tar.gz"
# Extract to a stable per-machine cache (NOT into the installed package, which
# may be read-only); the tarball is tiny so re-extraction is cheap.
_CACHE_DIR = Path(tempfile.gettempdir()) / "a2e_swe_bench_pro_harness"
_LOCK = threading.Lock()


def _ensure_extracted() -> Path:
    """Extract the vendored run_scripts tarball once; return its root dir."""
    run_scripts = _CACHE_DIR / "run_scripts"
    if run_scripts.is_dir():
        return run_scripts
    with _LOCK:
        if run_scripts.is_dir():
            return run_scripts
        if not _TARBALL.is_file():
            raise FileNotFoundError(
                f"vendored SWE-bench Pro harness tarball missing: {_TARBALL}"
            )
        _CACHE_DIR.mkdir(parents=True, exist_ok=True)
        with tarfile.open(_TARBALL, "r:gz") as tf:
            try:
                tf.extractall(_CACHE_DIR, filter="data")  # py>=3.12
            except TypeError:  # pragma: no cover - py<3.12 has no `filter`
                tf.extractall(_CACHE_DIR)
        logger.info("extracted SWE-bench Pro run_scripts to %s", _CACHE_DIR)
    return run_scripts


def get_instance_scripts(instance_id: str) -> tuple[str, str]:
    """Return ``(run_script_sh, parser_py)`` source text for an instance.

    Raises:
        FileNotFoundError: the instance has no vendored scripts (or the tarball
            is missing).
    """
    root = _ensure_extracted()
    inst_dir = root / instance_id
    run_script = inst_dir / "run_script.sh"
    parser = inst_dir / "parser.py"
    if not run_script.is_file() or not parser.is_file():
        raise FileNotFoundError(
            f"no vendored run_script/parser for instance {instance_id!r} (looked in {inst_dir})"
        )
    return run_script.read_text(), parser.read_text()


def has_instance_scripts(instance_id: str) -> bool:
    """True iff vendored grading scripts exist for ``instance_id``."""
    try:
        root = _ensure_extracted()
    except FileNotFoundError:
        return False
    inst_dir = root / instance_id
    return (inst_dir / "run_script.sh").is_file() and (inst_dir / "parser.py").is_file()
