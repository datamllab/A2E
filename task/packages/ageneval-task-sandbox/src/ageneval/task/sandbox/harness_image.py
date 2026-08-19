"""Build cached task images containing a complete Node.js coding harness."""

from __future__ import annotations

import hashlib
import os
import re
import subprocess
from collections.abc import Sequence
from pathlib import Path

from ageneval.task.sandbox.spec import SandboxSpec

_SAFE_IMAGE = re.compile(r"^[A-Za-z0-9][A-Za-z0-9._/@:+-]*$")
_SAFE_KIND = re.compile(r"^[a-z0-9][a-z0-9-]*$")
_IGNORED_PARTS = {".git", "dist", "node_modules", "test-dist", "__pycache__"}
_RUNTIME_FORMAT_VERSION = "3"
_COMPOSE_FORMAT_VERSION = "2"


class HarnessImageError(RuntimeError):
    """Raised when a containerized harness image cannot be prepared."""


def _source_digest(
    package_dir: Path,
    *,
    builder_image: str,
    kind: str,
    setup: str,
    rebuild_packages: Sequence[str],
) -> str:
    digest = hashlib.sha256()
    digest.update(
        (
            f"{_RUNTIME_FORMAT_VERSION}\0{builder_image}\0{kind}\0{setup}\0"
            f"{' '.join(rebuild_packages)}\0"
        ).encode()
    )
    for path in sorted(package_dir.rglob("*")):
        if not path.is_file() or any(part in _IGNORED_PARTS for part in path.parts):
            continue
        relative = path.relative_to(package_dir).as_posix()
        digest.update(relative.encode())
        digest.update(b"\0")
        digest.update(path.read_bytes())
        digest.update(b"\0")
    return digest.hexdigest()[:16]


def _run(command: list[str], *, cwd: Path, input: str | None = None) -> str:
    try:
        process = subprocess.run(
            command,
            cwd=cwd,
            input=input,
            capture_output=True,
            text=True,
            encoding="utf-8",
            errors="replace",
            timeout=3600,
        )
    except (FileNotFoundError, subprocess.TimeoutExpired) as exc:
        raise HarnessImageError(f"failed to run {' '.join(command)}: {exc}") from exc
    if process.returncode != 0:
        detail = (process.stderr or process.stdout)[-4000:]
        raise HarnessImageError(f"{' '.join(command)} failed:\n{detail}")
    return process.stdout.strip()


def prepare_node_harness_image(
    spec: SandboxSpec,
    *,
    package_dir: str | os.PathLike[str],
    kind: str,
    setup_command: str = "",
    rebuild_packages: Sequence[str] = (),
) -> SandboxSpec:
    """Return a Docker spec whose image contains the supplied harness package.

    The harness runtime and its composition with a benchmark base image are
    content-addressed separately. ``npm ci`` therefore runs once per harness
    source revision rather than once per benchmark image. Native modules are
    checked in the final task base and rebuilt there only when its libc is not
    compatible with the cached runtime. Windows host ``node_modules`` are
    never copied into benchmark containers.
    """

    if spec.type != "docker":
        return spec
    base_image = str(spec.config.get("image") or "")
    if not _SAFE_IMAGE.fullmatch(base_image):
        raise HarnessImageError(f"unsafe or missing Docker image name: {base_image!r}")
    if not _SAFE_KIND.fullmatch(kind):
        raise HarnessImageError(f"unsafe harness kind: {kind!r}")
    if any(not _SAFE_KIND.fullmatch(package) for package in rebuild_packages):
        raise HarnessImageError(f"unsafe npm rebuild package list: {rebuild_packages!r}")
    builder_image = os.environ.get("A2E_HARNESS_NODE_IMAGE", "node:22-bullseye-slim")
    if not _SAFE_IMAGE.fullmatch(builder_image):
        raise HarnessImageError(f"unsafe Node builder image name: {builder_image!r}")
    source = Path(package_dir).resolve()
    if not (source / "package.json").is_file() or not (source / "package-lock.json").is_file():
        raise HarnessImageError(f"harness package is incomplete: {source}")

    harness_digest = _source_digest(
        source,
        builder_image=builder_image,
        kind=kind,
        setup=setup_command,
        rebuild_packages=rebuild_packages,
    )
    runtime_image = f"a2e-local/{kind}-harness-runtime:{harness_digest}"
    runtime_inspected = subprocess.run(
        ["docker", "image", "inspect", runtime_image],
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="replace",
    )
    if runtime_inspected.returncode != 0:
        setup = f"RUN {setup_command}\n" if setup_command else ""
        rebuild = (
            f"RUN npm rebuild {' '.join(rebuild_packages)}\n" if rebuild_packages else ""
        )
        runtime_dockerfile = (
            "# syntax=docker/dockerfile:1\n"
            f"FROM {builder_image}\n"
            "WORKDIR /opt/a2e-harness\n"
            "COPY package.json package-lock.json ./\n"
            "RUN --mount=type=cache,target=/root/.npm "
            "npm ci --ignore-scripts --fetch-retries=5 "
            "--fetch-retry-mintimeout=20000 --fetch-retry-maxtimeout=120000\n"
            f"{rebuild}"
            "COPY . .\n"
            "RUN npm run build\n"
            "RUN mkdir -p /opt/a2e-dsh\n"
            f"{setup}"
        )
        _run(
            [
                "docker",
                "build",
                "--pull=false",
                "--tag",
                runtime_image,
                "--file",
                "-",
                ".",
            ],
            cwd=source,
            input=runtime_dockerfile,
        )

    image_digest = hashlib.sha256(
        f"{_COMPOSE_FORMAT_VERSION}\0{base_image}\0{runtime_image}".encode()
    ).hexdigest()[:16]
    image = f"a2e-local/{kind}-harness:{image_digest}"
    inspected = subprocess.run(
        ["docker", "image", "inspect", image],
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="replace",
    )
    if inspected.returncode != 0:
        if rebuild_packages:
            packages = " ".join(rebuild_packages)
            checks = " && ".join(
                f'node -e "require(\'/opt/a2e-harness/node_modules/{package}\')"'
                for package in rebuild_packages
            )
            dockerfile = (
                f"FROM {runtime_image} AS a2e-harness-build\n"
                f"FROM {builder_image} AS a2e-node-toolchain\n"
                f"FROM {base_image} AS a2e-task-build\n"
                "COPY --from=a2e-harness-build /usr/local/bin/node /usr/local/bin/node\n"
                "COPY --from=a2e-harness-build /opt/a2e-harness /opt/a2e-harness\n"
                "COPY --from=a2e-harness-build /opt/a2e-dsh /opt/a2e-dsh\n"
                "COPY --from=a2e-node-toolchain /usr/local/include/node "
                "/usr/local/include/node\n"
                "COPY --from=a2e-node-toolchain /usr/local/lib/node_modules/npm "
                "/usr/local/lib/node_modules/npm\n"
                f"RUN ({checks}) || (cd /opt/a2e-harness && "
                "npm_config_nodedir=/usr/local "
                "/usr/local/bin/node /usr/local/lib/node_modules/npm/bin/npm-cli.js "
                f"rebuild {packages})\n"
                f"FROM {base_image}\n"
                "COPY --from=a2e-task-build /usr/local/bin/node /usr/local/bin/node\n"
                "COPY --from=a2e-task-build /opt/a2e-harness /opt/a2e-harness\n"
                "COPY --from=a2e-task-build /opt/a2e-dsh /opt/a2e-dsh\n"
            )
        else:
            dockerfile = (
                f"FROM {runtime_image} AS a2e-harness-build\n"
                f"FROM {base_image}\n"
                "COPY --from=a2e-harness-build /usr/local/bin/node /usr/local/bin/node\n"
                "COPY --from=a2e-harness-build /opt/a2e-harness /opt/a2e-harness\n"
                "COPY --from=a2e-harness-build /opt/a2e-dsh /opt/a2e-dsh\n"
            )
        _run(
            ["docker", "build", "--pull=false", "--tag", image, "--file", "-", "."],
            cwd=source,
            input=dockerfile,
        )

    config = dict(spec.config)
    config["image"] = image
    config["pull"] = False
    return SandboxSpec(type=spec.type, config=config)
