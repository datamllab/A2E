"""LocalSandboxEnvironment — a temp-directory + subprocess sandbox.

No isolation guarantees (it runs on the host); a generic provider for offline
sandbox use where pulling a docker image is undesirable. Modelled on inspect_ai's
``util/_sandbox/local.py`` (MIT, UK AISI), made synchronous.
"""

from __future__ import annotations

import logging
import shutil
import subprocess
import tempfile
from pathlib import Path
from typing import Mapping

from ageneval.task.sandbox.environment import ExecResult, SandboxEnvironment
from ageneval.task.sandbox.registry import sandboxenv

logger = logging.getLogger(__name__)


@sandboxenv("local")
class LocalSandboxEnvironment(SandboxEnvironment):
    """Run commands in a per-task temp directory via ``subprocess``."""

    def __init__(self, cwd: str | None = None, **_ignored: object) -> None:
        # ``cwd`` lets a dataset pin a working dir; otherwise a fresh temp dir.
        self._explicit_cwd = cwd
        self._tmp: tempfile.TemporaryDirectory[str] | None = None
        self._workdir: str = cwd or "."

    def start(self) -> None:
        if self._explicit_cwd is None:
            self._tmp = tempfile.TemporaryDirectory(prefix="a2e-sandbox-")
            self._workdir = self._tmp.name

    def cleanup(self) -> None:
        if self._tmp is not None:
            self._tmp.cleanup()
            self._tmp = None

    def _resolve(self, path: str) -> str:
        p = Path(path)
        return str(p if p.is_absolute() else Path(self._workdir) / p)

    def exec(
        self,
        cmd: list[str],
        *,
        cwd: str | None = None,
        env: Mapping[str, str] | None = None,
        input: str | None = None,
        timeout: int | None = None,
    ) -> ExecResult:
        run_cwd = self._resolve(cwd) if cwd else self._workdir
        try:
            proc = subprocess.run(
                cmd,
                cwd=run_cwd,
                env=dict(env) if env is not None else None,
                input=input,
                capture_output=True,
                text=True,
                timeout=timeout,
            )
        except subprocess.TimeoutExpired as exc:
            return ExecResult(False, 124, exc.stdout or "", f"timeout after {timeout}s")
        except FileNotFoundError as exc:
            return ExecResult(False, 127, "", str(exc))
        return ExecResult(proc.returncode == 0, proc.returncode, proc.stdout, proc.stderr)

    def write_file(self, path: str, contents: str | bytes) -> None:
        target = Path(self._resolve(path))
        target.parent.mkdir(parents=True, exist_ok=True)
        if isinstance(contents, bytes):
            target.write_bytes(contents)
        else:
            target.write_text(contents)

    def read_file(self, path: str, text: bool = True) -> str | bytes:
        target = Path(self._resolve(path))
        return target.read_text() if text else target.read_bytes()

    def connection(self) -> str:
        return f"cd {self._workdir} && bash"
