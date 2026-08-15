from __future__ import annotations

import subprocess

from ageneval.task.sandbox import SandboxSpec
from ageneval.task.sandbox.harness_image import prepare_node_harness_image


def test_builds_a_content_addressed_harness_image(monkeypatch, tmp_path) -> None:
    (tmp_path / "package.json").write_text('{"scripts":{"build":"tsc"}}')
    (tmp_path / "package-lock.json").write_text("{}")
    (tmp_path / "source.ts").write_text("export const value = 1;")
    calls: list[tuple[list[str], str | None]] = []

    def run(command, **kwargs):
        calls.append((command, kwargs.get("input")))
        return subprocess.CompletedProcess(
            command,
            1 if command[:3] == ["docker", "image", "inspect"] else 0,
            stdout="",
            stderr="missing" if command[:3] == ["docker", "image", "inspect"] else "",
        )

    monkeypatch.setattr(subprocess, "run", run)
    monkeypatch.setenv("A2E_HARNESS_NODE_IMAGE", "node:22-bullseye-slim")
    spec = SandboxSpec(
        type="docker",
        config={"image": "example/task:latest", "cwd": "/workspace"},
    )
    prepared = prepare_node_harness_image(
        spec,
        package_dir=tmp_path,
        kind="pi",
    )

    assert prepared.config["image"].startswith("a2e-local/pi-harness:")
    assert prepared.config["pull"] is False
    assert prepared.config["cwd"] == "/workspace"
    dockerfile = calls[-1][1]
    assert "FROM node:22-bullseye-slim AS a2e-harness-build" in dockerfile
    assert "FROM example/task:latest" in dockerfile
    assert "COPY --from=a2e-harness-build /opt/a2e-harness" in dockerfile


def test_non_docker_specs_are_unchanged(tmp_path) -> None:
    spec = SandboxSpec(type="local", config={"cwd": str(tmp_path)})
    assert prepare_node_harness_image(
        spec,
        package_dir=tmp_path,
        kind="pi",
    ) is spec
