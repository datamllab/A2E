"""Synchronous sandbox environment base class + ExecResult.

Migrated and simplified from inspect_ai's ``util/_sandbox/environment.py``
(MIT, UK AI Security Institute). Differences from upstream:

* **Synchronous** API (``subprocess`` / ``docker exec``) — matches A2E's sync
  ``AgentBinding.tool_executor`` contract; sandbox eval runs serially.
* **Instance-level lifecycle** (``start`` / ``cleanup``) instead of the
  task/sample classmethod lifecycle — A2E needs exactly one container per task.
"""

from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass
from typing import Mapping


@dataclass(frozen=True)
class ExecResult:
    """Result of running a command inside a sandbox.

    Attributes:
        success: ``True`` iff ``returncode == 0``.
        returncode: Process exit code.
        stdout: Captured standard output (decoded text).
        stderr: Captured standard error (decoded text).
    """

    success: bool
    returncode: int
    stdout: str
    stderr: str


class SandboxEnvironment(ABC):
    """An isolated environment for executing commands and moving files.

    Concrete providers (``local``, ``docker``) register themselves via the
    ``@sandboxenv(name)`` decorator and are instantiated through
    ``create_sandbox(spec)`` which also calls :meth:`start`.

    Subclasses must implement :meth:`exec`, :meth:`write_file`,
    :meth:`read_file`. :meth:`start` / :meth:`cleanup` default to no-ops so a
    trivial provider need not override them.
    """

    type: str = "base"

    @abstractmethod
    def exec(
        self,
        cmd: list[str],
        *,
        cwd: str | None = None,
        env: Mapping[str, str] | None = None,
        input: str | None = None,
        timeout: int | None = None,
    ) -> ExecResult:
        """Run ``cmd`` (argv list) inside the sandbox and capture its output."""
        raise NotImplementedError

    @abstractmethod
    def write_file(self, path: str, contents: str | bytes) -> None:
        """Write ``contents`` to ``path`` inside the sandbox (creating parents)."""
        raise NotImplementedError

    @abstractmethod
    def read_file(self, path: str, text: bool = True) -> str | bytes:
        """Read ``path`` from inside the sandbox (text by default)."""
        raise NotImplementedError

    def start(self) -> None:
        """Provision the environment (temp dir / container). Default: no-op."""

    def cleanup(self) -> None:
        """Tear the environment down. Default: no-op. Must never raise."""

    def connection(self) -> str:
        """Human-facing shell command to attach to this sandbox (debugging)."""
        return ""
