"""Active-sandbox context variable + lifecycle context manager.

``sandbox()`` returns the sandbox for the current task (set by
``sandbox_session``). The primary way a tool reaches the sandbox is via the
injected ``state["__sandbox__"]`` handle (see SandboxScoringRunner); this
contextvar is the fallback / the channel a grader uses directly.
"""

from __future__ import annotations

import logging
from contextlib import contextmanager
from contextvars import ContextVar
from typing import Iterator

from ageneval.task.sandbox.environment import SandboxEnvironment
from ageneval.task.sandbox.registry import create_sandbox
from ageneval.task.sandbox.spec import SandboxSpec

logger = logging.getLogger(__name__)

_active: ContextVar[SandboxEnvironment | None] = ContextVar(
    "a2e_active_sandbox", default=None
)


def sandbox() -> SandboxEnvironment:
    """Return the active sandbox for the current task.

    Raises:
        RuntimeError: when called outside a ``sandbox_session`` (no sandbox set).
    """
    sb = _active.get()
    if sb is None:
        raise RuntimeError(
            "no active sandbox; sandbox tools must run inside sandbox_session(...)"
        )
    return sb


@contextmanager
def sandbox_session(spec: SandboxSpec) -> Iterator[SandboxEnvironment]:
    """Create the sandbox for ``spec``, bind it as active, clean up on exit.

    The environment is started by ``create_sandbox``; cleanup always runs (even
    on exception) so containers / temp dirs never leak.
    """
    sb = create_sandbox(spec)
    token = _active.set(sb)
    try:
        yield sb
    finally:
        _active.reset(token)
        try:
            sb.cleanup()
        except Exception as exc:  # noqa: BLE001 — cleanup must never mask the body
            logger.warning("sandbox cleanup failed: %s", exc)
