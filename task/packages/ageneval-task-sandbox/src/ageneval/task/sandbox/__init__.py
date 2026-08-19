"""A2E sandbox abstraction — sync execution environments for code datasets.

Public API:
    SandboxEnvironment, ExecResult   — base interface + command result
    SandboxSpec                      — JSON-friendly provider spec
    sandbox(), sandbox_session(spec) — active-sandbox accessor + lifecycle CM
    create_sandbox(spec)             — factory (start()s the env)
    find_sandboxenv(type), sandboxenv(name) — registry lookup + decorator
    LocalSandboxEnvironment, DockerSandboxEnvironment — built-in providers
"""

from ageneval.task.sandbox.cleanup import sweep_sandbox_containers
from ageneval.task.sandbox.context import sandbox, sandbox_session
from ageneval.task.sandbox.docker import DockerSandboxEnvironment
from ageneval.task.sandbox.environment import ExecResult, SandboxEnvironment
from ageneval.task.sandbox.harness_image import HarnessImageError, prepare_node_harness_image
from ageneval.task.sandbox.local import LocalSandboxEnvironment
from ageneval.task.sandbox.registry import create_sandbox, find_sandboxenv, sandboxenv
from ageneval.task.sandbox.spec import SandboxSpec

__all__ = [
    "DockerSandboxEnvironment",
    "ExecResult",
    "HarnessImageError",
    "LocalSandboxEnvironment",
    "SandboxEnvironment",
    "SandboxSpec",
    "create_sandbox",
    "find_sandboxenv",
    "prepare_node_harness_image",
    "sandbox",
    "sandbox_session",
    "sandboxenv",
    "sweep_sandbox_containers",
]
