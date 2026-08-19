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
    dockerfiles = [body for command, body in calls if command[:2] == ["docker", "build"]]
    assert len(dockerfiles) == 2
    runtime_dockerfile, compose_dockerfile = dockerfiles
    assert "# syntax=docker/dockerfile:1" in runtime_dockerfile
    assert "FROM node:22-bullseye-slim" in runtime_dockerfile
    assert "--mount=type=cache,target=/root/.npm" in runtime_dockerfile
    assert "--fetch-retries=5" in runtime_dockerfile
    assert "FROM a2e-local/pi-harness-runtime:" in compose_dockerfile
    assert "FROM example/task:latest" in compose_dockerfile
    assert "COPY --from=a2e-harness-build /opt/a2e-harness" in compose_dockerfile


def test_non_docker_specs_are_unchanged(tmp_path) -> None:
    spec = SandboxSpec(type="local", config={"cwd": str(tmp_path)})
    assert prepare_node_harness_image(
        spec,
        package_dir=tmp_path,
        kind="pi",
    ) is spec


def test_rebuilds_incompatible_native_modules_in_the_task_base(
    monkeypatch, tmp_path
) -> None:
    (tmp_path / "package.json").write_text('{"scripts":{"build":"tsc"}}')
    (tmp_path / "package-lock.json").write_text("{}")
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
    spec = SandboxSpec(type="docker", config={"image": "example/old-glibc:latest"})
    prepare_node_harness_image(
        spec,
        package_dir=tmp_path,
        kind="deepseek",
        rebuild_packages=("node-pty",),
    )

    dockerfiles = [body for command, body in calls if command[:2] == ["docker", "build"]]
    compose_dockerfile = dockerfiles[-1]
    assert "FROM node:22-bullseye-slim AS a2e-node-toolchain" in compose_dockerfile
    assert "FROM example/old-glibc:latest AS a2e-task-build" in compose_dockerfile
    assert "require('/opt/a2e-harness/node_modules/node-pty')" in compose_dockerfile
    assert "npm_config_nodedir=/usr/local" in compose_dockerfile
    assert "rebuild node-pty" in compose_dockerfile
