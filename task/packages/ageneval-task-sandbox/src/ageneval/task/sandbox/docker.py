"""DockerSandboxEnvironment — a single-container sandbox via the docker CLI.

Uses ``docker run/exec/cp/rm`` directly (no docker-compose) so it works with a
legacy docker install that lacks the compose plugin. One container per task,
matching SWE-bench's one-image-per-instance model. Inspired by inspect_ai's
docker provider (MIT, UK AISI) but reduced to the single-container case and
made synchronous.
"""

from __future__ import annotations

import logging
import os
import shlex
import subprocess
import tempfile
from pathlib import PurePosixPath
from typing import Mapping, Sequence

from ageneval.task.sandbox.environment import ExecResult, SandboxEnvironment
from ageneval.task.sandbox.registry import sandboxenv

logger = logging.getLogger(__name__)

# Docker label stamped on every A2E-created sandbox container so the leak-sweep
# (cleanup.sweep_sandbox_containers) can identify and remove only our containers.
A2E_SANDBOX_LABEL = "a2e.sandbox=1"

# In-container timeout exit codes (coreutils `timeout`): 124 hard, 137 SIGKILL.
_TIMEOUT_CODES = (124, 137, 143)


class DockerError(RuntimeError):
    """Raised when the docker CLI is missing or a lifecycle command fails."""


@sandboxenv("docker")
class DockerSandboxEnvironment(SandboxEnvironment):
    """Run commands inside one detached container started from ``image``."""

    def __init__(
        self,
        image: str | None = None,
        *,
        cwd: str = "/testbed",
        pull: bool = True,
        user: str | None = None,
        entrypoint: str | None = None,
        keepalive: Sequence[str] = ("sleep", "infinity"),
        volumes: Sequence[str] = (),
        **_ignored: object,
    ) -> None:
        if not image:
            raise DockerError("docker sandbox requires an 'image' in its config")
        self.image = image
        self.workdir = cwd
        self.pull = pull
        self.user = user
        # Some images ship an ENTRYPOINT (e.g. SWE-bench Pro images use
        # ENTRYPOINT ["/bin/bash"]), which would swallow the keepalive command
        # and make the container exit immediately. Allow overriding it so the
        # keepalive (e.g. `sleep infinity`) runs as the actual process.
        self.entrypoint = entrypoint
        self.keepalive = list(keepalive)
        self.volumes = [str(volume) for volume in volumes]
        self._cid: str | None = None

    # ── lifecycle ──────────────────────────────────────────────────────────
    def start(self) -> None:
        if not _docker_available():
            raise DockerError(
                "docker CLI not available on PATH; install docker to run sandbox datasets"
            )
        if self.pull and not _image_present_locally(self.image):
            logger.info("docker pull %s", self.image)
            pulled = _run(["docker", "pull", self.image], timeout=3600)
            if pulled.returncode != 0:
                raise DockerError(f"docker pull {self.image} failed:\n{pulled.stderr[-2000:]}")
        # Label every A2E sandbox container so leak-sweep can find them later
        # (see cleanup.sweep_sandbox_containers). Belt-and-suspenders on top of
        # the per-container ``--rm`` + cleanup() finally.
        run_cmd = ["docker", "run", "-d", "--rm", "--label", A2E_SANDBOX_LABEL]
        if self.user:
            run_cmd += ["--user", self.user]
        if self.entrypoint:
            run_cmd += ["--entrypoint", self.entrypoint]
        for volume in self.volumes:
            run_cmd += ["--volume", volume]
        run_cmd += [self.image, *self.keepalive]
        res = _run(run_cmd, timeout=120)
        if res.returncode != 0 or not res.stdout.strip():
            raise DockerError(f"docker run failed for {self.image}:\n{res.stderr[-2000:]}")
        self._cid = res.stdout.strip()
        logger.info("started container %s from %s", self._cid[:12], self.image)

    def cleanup(self) -> None:
        if self._cid:
            _run(["docker", "rm", "-f", self._cid], timeout=60)
            self._cid = None

    # ── exec / files ───────────────────────────────────────────────────────
    def exec(
        self,
        cmd: list[str],
        *,
        cwd: str | None = None,
        env: Mapping[str, str] | None = None,
        input: str | None = None,
        timeout: int | None = None,
    ) -> ExecResult:
        if self._cid is None:
            raise DockerError("container not started")
        args = ["docker", "exec"]
        if input is not None:
            args.append("-i")
        args += ["-w", cwd or self.workdir]
        for key, value in (env or {}).items():
            args += ["-e", f"{key}={value}"]
        in_container = list(cmd)
        if timeout is not None:
            in_container = ["timeout", "-k", "5s", f"{timeout}s", *cmd]
        args += [self._cid, *in_container]
        host_timeout = (timeout + 15) if timeout is not None else None
        res = _run(args, input=input, timeout=host_timeout)
        if timeout is not None and res.returncode in _TIMEOUT_CODES:
            return ExecResult(False, res.returncode, res.stdout, f"timed out after {timeout}s")
        return ExecResult(res.returncode == 0, res.returncode, res.stdout, res.stderr)

    def write_file(self, path: str, contents: str | bytes) -> None:
        if self._cid is None:
            raise DockerError("container not started")
        abs_path = self._abs(path)
        parent = str(PurePosixPath(abs_path).parent)
        mk = self.exec(["mkdir", "-p", parent])
        if not mk.success:
            raise DockerError(f"mkdir -p {parent} failed: {mk.stderr[-500:]}")
        data = contents.encode() if isinstance(contents, str) else contents
        with tempfile.NamedTemporaryFile(delete=False) as tmp:
            tmp.write(data)
            host_path = tmp.name
        try:
            res = _run(["docker", "cp", host_path, f"{self._cid}:{abs_path}"], timeout=120)
            if res.returncode != 0:
                raise DockerError(f"docker cp into container failed: {res.stderr[-500:]}")
        finally:
            os.unlink(host_path)

    def read_file(self, path: str, text: bool = True) -> str | bytes:
        if self._cid is None:
            raise DockerError("container not started")
        abs_path = self._abs(path)
        with tempfile.NamedTemporaryFile(delete=False) as tmp:
            host_path = tmp.name
        try:
            res = _run(["docker", "cp", f"{self._cid}:{abs_path}", host_path], timeout=120)
            if res.returncode != 0:
                raise FileNotFoundError(f"read_file {abs_path}: {res.stderr[-500:]}")
            with open(host_path, "r" if text else "rb") as fh:
                return fh.read()
        finally:
            os.unlink(host_path)

    def connection(self) -> str:
        return f"docker exec -it {self._cid or '<container>'} bash"

    def _abs(self, path: str) -> str:
        p = PurePosixPath(path)
        return str(p if p.is_absolute() else PurePosixPath(self.workdir) / p)


# ── docker CLI helpers ──────────────────────────────────────────────────────
def _run(cmd: list[str], *, input: str | None = None, timeout: int | None = None) -> ExecResult:
    """Run a host docker CLI command, capturing output (never raises on nonzero)."""
    try:
        proc = subprocess.run(
            cmd, input=input, capture_output=True, text=True, timeout=timeout
        )
    except subprocess.TimeoutExpired as exc:
        return ExecResult(False, 124, exc.stdout or "", f"host timeout after {timeout}s: {shlex.join(cmd)}")
    except FileNotFoundError as exc:
        return ExecResult(False, 127, "", str(exc))
    return ExecResult(proc.returncode == 0, proc.returncode, proc.stdout, proc.stderr)


def _docker_available() -> bool:
    return _run(["docker", "version", "--format", "{{.Server.Version}}"], timeout=30).success


def _image_present_locally(image: str) -> bool:
    return _run(["docker", "image", "inspect", image], timeout=60).success
