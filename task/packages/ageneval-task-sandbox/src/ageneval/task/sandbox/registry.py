"""Sandbox provider registry + factory.

Mirrors inspect_ai's ``@sandboxenv`` decorator + ``registry_find_sandboxenv``
(MIT, UK AISI), trimmed to A2E's needs. Providers self-register at import time;
``create_sandbox(spec)`` instantiates the right class and calls ``.start()``.
"""

from __future__ import annotations

import logging
from typing import Callable, Type

from ageneval.task.sandbox.environment import SandboxEnvironment
from ageneval.task.sandbox.spec import SandboxSpec

logger = logging.getLogger(__name__)

_REGISTRY: dict[str, Type[SandboxEnvironment]] = {}


def sandboxenv(name: str) -> Callable[[Type[SandboxEnvironment]], Type[SandboxEnvironment]]:
    """Class decorator: register a SandboxEnvironment subclass under ``name``."""

    def wrapper(cls: Type[SandboxEnvironment]) -> Type[SandboxEnvironment]:
        cls.type = name
        _REGISTRY[name] = cls
        return cls

    return wrapper


def find_sandboxenv(type: str) -> Type[SandboxEnvironment]:
    """Look up a registered provider class by name, else raise a clear error."""
    # Import side-effect: ensure built-in providers are registered. Done lazily
    # to avoid an import cycle (providers import this module).
    if not _REGISTRY:
        from ageneval.task.sandbox import local, docker  # noqa: F401

    cls = _REGISTRY.get(type)
    if cls is None:
        raise ValueError(
            f"Unknown sandbox type {type!r}. Registered: {sorted(_REGISTRY)}."
        )
    return cls


def create_sandbox(spec: SandboxSpec) -> SandboxEnvironment:
    """Instantiate the provider for ``spec`` and start it (container / temp dir)."""
    cls = find_sandboxenv(spec.type)
    sandbox = cls(**dict(spec.config))  # type: ignore[call-arg]
    sandbox.start()
    return sandbox
