"""SandboxSpec — a JSON-friendly description of which sandbox to create.

The spec must survive a round-trip through A2E dataset metadata (plain
JSON), so it is a tiny frozen dataclass over ``type`` + a ``config`` dict.
``TaskInput.sandbox`` carries one of these (as a plain dict on the wire).
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Mapping


@dataclass(frozen=True)
class SandboxSpec:
    """Which sandbox provider to use and how to configure it.

    Attributes:
        type: Provider name registered via ``@sandboxenv`` (``"local"`` / ``"docker"``).
        config: Provider-specific options. For ``docker``:
            ``{"image": "<image>", "cwd": "/testbed", "pull": True}``.
    """

    type: str
    config: Mapping[str, Any] = field(default_factory=dict)

    @staticmethod
    def from_obj(obj: Any) -> "SandboxSpec | None":
        """Coerce a str / dict / SandboxSpec / None into a SandboxSpec | None.

        * ``None`` → ``None`` (dataset has no sandbox).
        * ``"docker"`` → ``SandboxSpec("docker")``.
        * ``{"type": "docker", "config": {...}}`` → ``SandboxSpec("docker", {...})``.
        * ``SandboxSpec`` → unchanged.
        """
        if obj is None:
            return None
        if isinstance(obj, SandboxSpec):
            return obj
        if isinstance(obj, str):
            return SandboxSpec(type=obj)
        if isinstance(obj, Mapping):
            t = obj.get("type")
            if not t:
                return None
            cfg = obj.get("config") or {}
            return SandboxSpec(type=str(t), config=dict(cfg))
        raise TypeError(f"cannot coerce {type(obj)!r} into SandboxSpec")

    def to_dict(self) -> dict[str, Any]:
        """Serialize for upload into A2E dataset metadata."""
        return {"type": self.type, "config": dict(self.config)}
