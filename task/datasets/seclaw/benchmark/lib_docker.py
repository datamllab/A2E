# Copyright 2025 Anthropic, Inc.
#
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
#     http://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
# See the License for the specific language governing permissions and
# limitations under the License.

"""Docker container lifecycle management for per-task isolation.

Each task run gets its own fresh Docker container from the OpenClaw image.
The container is started, fixtures are deployed, the agent runs, artifacts
are collected, and the container is destroyed.

Inspired by QwenClawBench's Docker-per-task model, adapted for the
OpenClaw Safety Bench fixture structure (init.sh, workspace/, mcp/, mock_service/).
See: https://github.com/SKYLENAGE-AI/QwenClawBench
"""

import hashlib
import json
import logging
import os
import posixpath
import re
import shlex
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path

logger = logging.getLogger(__name__)

DEFAULT_IMAGE = "ghcr.io/openclaw/openclaw:main"
CONTAINER_LABEL = "openclaw-safety-bench=1"
DOCKER_HOMES_BASE = Path(tempfile.gettempdir()) / "openclaw-safety-bench" / "docker_homes"
DEFAULT_WORKSPACE_PATH = "/home/node/workspace"


def _health_check_candidates(fixture_dir: Path) -> list[tuple[int, str]]:
    """Return localhost health endpoints declared by task fixture files."""
    candidates: list[tuple[int, str]] = []
    for path in fixture_dir.rglob("*"):
        if not path.is_file() or path.suffix not in {".py", ".sh"}:
            continue
        try:
            text = path.read_text(encoding="utf-8", errors="ignore")
        except OSError:
            continue
        for port, endpoint in re.findall(r"http://localhost:(\d+)(/(?:[A-Za-z0-9_-]+/)?health)", text):
            candidates.append((int(port), endpoint))

    seen: set[tuple[int, str]] = set()
    unique: list[tuple[int, str]] = []
    for candidate in candidates:
        if candidate not in seen:
            seen.add(candidate)
            unique.append(candidate)
    return unique


def _redact_command(cmd: list[str]) -> str:
    """Return a log-safe command string with known secret flags redacted."""
    text = " ".join(cmd)
    for flag in ("--custom-api-key", "--api-key", "--judge-api-key"):
        text = text.replace(f"{flag} '", f"{flag} '***")
        text = text.replace(f'{flag} "', f'{flag} "***')
    import re
    text = re.sub(r"(--custom-api-key\s+)'[^']*'", r"\1'***'", text)
    text = re.sub(r'(--custom-api-key\s+)"[^"]*"', r'\1"***"', text)
    text = re.sub(r"(--api-key\s+)'[^']*'", r"\1'***'", text)
    text = re.sub(r'(--api-key\s+)"[^"]*"', r'\1"***"', text)
    text = re.sub(r"(--judge-api-key\s+)'[^']*'", r"\1'***'", text)
    text = re.sub(r'(--judge-api-key\s+)"[^"]*"', r'\1"***"', text)
    return text


def _run_docker(args: list[str], timeout: int = 120) -> subprocess.CompletedProcess:
    """Run a docker CLI command and return the result."""
    cmd = ["docker"] + args
    logger.debug("Running: %s", _redact_command(cmd))
    return subprocess.run(cmd, capture_output=True, text=True, timeout=timeout)


def _run_docker_check(args: list[str], timeout: int = 120) -> str:
    """Run a docker CLI command, raising on failure."""
    result = _run_docker(args, timeout)
    if result.returncode != 0:
        raise RuntimeError(
            f"Docker command failed: {' '.join(args)}\n"
            f"stdout: {result.stdout}\nstderr: {result.stderr}"
        )
    return result.stdout.strip()


DEFAULT_INIT_TIMEOUT = 300  # seconds for init.sh (pip install can be slow)


def _container_name(run_id: str, task_id: str) -> str:
    """Return a readable, deterministic Docker container name for a task run."""
    task_hash = hashlib.sha1(task_id.encode("utf-8")).hexdigest()[:10]
    return f"osb-{run_id}-{task_id[:32]}-{task_hash}"


def _find_host_pip_wheel() -> Path | None:
    """Return a bundled pip wheel from the host Python, if available."""
    candidates: list[Path] = []
    try:
        import ensurepip

        bundled = Path(ensurepip.__file__).resolve().parent / "_bundled"
        candidates.extend(sorted(bundled.glob("pip-*.whl")))
    except Exception:
        pass

    for prefix in {Path(sys.prefix), Path(sys.base_prefix)}:
        candidates.extend(sorted((prefix / "lib").glob("python*/ensurepip/_bundled/pip-*.whl")))

    existing = [path for path in candidates if path.exists()]
    return existing[-1] if existing else None


def _patch_init_script_for_docker(content: str) -> str:
    """Patch common generated init.sh patterns that are brittle in Docker."""

    def fix_mcp_set(match: re.Match[str]) -> str:
        name = match.group("name")
        command = match.group("command")
        args = [
            value.strip().strip('"').strip("'")
            for value in match.group("args").split()
            if value.strip()
        ]
        config = json.dumps({"command": command, "args": args})
        return f"openclaw mcp set {name} '{config}'"

    content = re.sub(
        r"openclaw\s+mcp\s+set\s+(?P<name>\S+)\s+--command\s+(?P<command>\S+)\s+--args\s+(?P<args>.+?)(?:\s*2>/dev/null|\s*\|\||\s*&&|\s*;|$)",
        fix_mcp_set,
        content,
    )

    def make_curl_assignment_nonfatal(match: re.Match[str]) -> str:
        line = match.group(0)
        if "|| true" in line:
            return line
        return f"{match.group(1)} || true{match.group(2)}"

    return re.sub(
        r"(?m)^(\s*[A-Za-z_][A-Za-z0-9_]*=\$\(curl\b[^\n)]*2>/dev/null)(\))",
        make_curl_assignment_nonfatal,
        content,
    )


class DockerContainer:
    """Manages a single Docker container for task execution."""

    def __init__(
        self,
        task_id: str,
        run_id: str,
        image: str = DEFAULT_IMAGE,
        openclaw_config_dir: Path | None = None,
        env_file: Path | None = None,
        timeout_seconds: int = 600,
        init_timeout: int = DEFAULT_INIT_TIMEOUT,
    ):
        self.task_id = task_id
        self.run_id = run_id
        self.image = image
        self.openclaw_config_dir = openclaw_config_dir
        self.env_file = env_file
        self.timeout_seconds = timeout_seconds
        self.init_timeout = init_timeout

        self.container_name = _container_name(run_id, task_id)
        self.container_id: str | None = None
        self.docker_home = DOCKER_HOMES_BASE / self.container_name
        self._started = False

    def start(self) -> None:
        """Start the Docker container with OpenClaw image."""
        if self._started:
            return

        # Prepare per-container openclaw home directory
        self.docker_home.mkdir(parents=True, exist_ok=True)

        if self.openclaw_config_dir and self.openclaw_config_dir.exists():
            # Copy openclaw config (exclude agents/ dir, pass .env separately)
            for item in self.openclaw_config_dir.iterdir():
                if item.name == "agents":
                    continue
                if item.name == ".env":
                    self.env_file = item
                    continue
                dest = self.docker_home / item.name
                if item.is_dir():
                    shutil.copytree(item, dest)
                else:
                    shutil.copy2(item, dest)

        # Create agents directory (fresh for each container)
        (self.docker_home / "agents").mkdir(parents=True, exist_ok=True)

        # Start container in detached mode; sleep indefinitely to keep it alive
        run_args = [
            "run",
            "-d",
            "--name", self.container_name,
            "--label", CONTAINER_LABEL,
            "-v", f"{self.docker_home}:/home/node/.openclaw",
        ]

        if self.env_file and self.env_file.exists():
            run_args.extend(["--env-file", str(self.env_file)])

        # Keep container alive with sleep
        run_args.extend([self.image, "sleep", "infinity"])

        self.container_id = _run_docker_check(run_args)
        self._started = True

        # Fix ownership of mounted openclaw home (node user = uid 1000)
        self.exec("chown -R 1000:1000 /home/node/.openclaw", user="root")

        logger.debug("Container started: %s (id: %s)", self.container_name, self.container_id[:12])

    def exec(self, command: str, user: str = "node", timeout: int | None = None) -> tuple[int, str, str]:
        """Execute a command inside the container.

        Returns:
            Tuple of (exit_code, stdout, stderr).
        """
        if not self._started:
            raise RuntimeError(f"Container {self.container_name} not started")

        timeout = timeout or self.timeout_seconds
        args = [
            "exec",
            "--user", user,
            self.container_name,
            "bash", "-c", command,
        ]

        result = _run_docker(args, timeout=timeout)
        return result.returncode, result.stdout, result.stderr

    def copy_into(self, src: Path, dest: str, user: str = "node") -> None:
        """Copy a file or directory into the container.

        Args:
            src: Local source path.
            dest: Destination path inside the container (absolute).
            user: Container user to own the files.
        """
        if not self._started:
            raise RuntimeError(f"Container {self.container_name} not started")

        if src.is_dir():
            # Copy directory contents
            _run_docker_check(["cp", str(src) + "/.", f"{self.container_name}:{dest}"])
        else:
            # Ensure parent directory exists
            parent = str(Path(dest).parent)
            self.exec(f"mkdir -p {parent}")
            _run_docker_check(["cp", str(src), f"{self.container_name}:{dest}"])

        # Fix ownership (must be root to chown files copied from host)
        self.exec(f"chown -R {user}:{user} {dest}", user="root")

    def copy_out(self, container_path: str, local_dest: Path) -> None:
        """Copy a file or directory out of the container.

        Args:
            container_path: Path inside the container.
            local_dest: Local destination path.
        """
        if not self._started:
            raise RuntimeError(f"Container {self.container_name} not started")

        local_dest.mkdir(parents=True, exist_ok=True)
        _run_docker_check(["cp", f"{self.container_name}:{container_path}/.", str(local_dest)])

    def prepare_workspace_paths(self, task_workspace_path: str | None = None) -> None:
        """Prepare Docker's workspace and ARCA-compatible workspace aliases.

        Docker/OpenClaw stores and snapshots the real workspace at
        /home/node/workspace. Many ARCA-designed tasks declare /opt/workspace in
        task.yaml or use that path from init.sh. Keep the real directory stable
        and expose compatible aliases before fixture init runs.
        """
        workspace_path = (task_workspace_path or DEFAULT_WORKSPACE_PATH).strip()
        if not workspace_path.startswith("/"):
            logger.warning(
                "[%s] Ignoring non-absolute workspace path %r",
                self.task_id, workspace_path,
            )
            workspace_path = DEFAULT_WORKSPACE_PATH
        workspace_path = workspace_path.rstrip("/") or "/"

        default_q = shlex.quote(DEFAULT_WORKSPACE_PATH)
        self.exec(f"mkdir -p {default_q}", user="root")
        self.exec(f"chown -R node:node {default_q}", user="root")
        self.exec(f"chmod -R u+rw {default_q}", user="root")

        def ensure_workspace_alias(alias_path: str) -> None:
            alias_path = alias_path.rstrip("/") or "/"
            if alias_path in {DEFAULT_WORKSPACE_PATH, "/"}:
                return

            workspace_q = shlex.quote(alias_path)
            parent_q = shlex.quote(posixpath.dirname(alias_path) or "/")
            alias_cmd = f"""
set -e
mkdir -p {parent_q}
if [ -L {workspace_q} ]; then
  ln -sfn {default_q} {workspace_q}
elif [ ! -e {workspace_q} ]; then
  ln -sfn {default_q} {workspace_q}
elif [ -d {workspace_q} ]; then
  if [ -z "$(find {workspace_q} -mindepth 1 -maxdepth 1 -print -quit)" ]; then
    rmdir {workspace_q}
    ln -sfn {default_q} {workspace_q}
  else
    echo 'workspace path already exists as a non-empty directory; leaving it in place' >&2
  fi
else
  echo 'workspace path exists and is not a directory or symlink' >&2
  exit 1
fi
chown -h node:node {workspace_q} 2>/dev/null || true
"""
            exit_code, stdout, stderr = self.exec(alias_cmd, user="root")
            if exit_code != 0:
                logger.warning(
                    "[%s] Failed to prepare workspace alias %s -> %s: %s%s",
                    self.task_id, alias_path, DEFAULT_WORKSPACE_PATH, stdout, stderr,
                )

        for alias_path in dict.fromkeys([workspace_path, "/opt/workspace"]):
            ensure_workspace_alias(alias_path)

    def _ensure_python(self) -> None:
        """Ensure Python3 and pip are available in the container.

        The native OpenClaw image is Node.js-based and may not include Python.
        Task fixtures (MCP/mock services) typically need Python + pip.
        """
        # Use init_timeout for Python/pip installation since it can be slow
        # in fresh containers with slow network.
        pip_timeout = max(self.init_timeout, 300)
        pip_index = os.environ.get("PIP_INDEX_URL", "")
        if not pip_index:
            _, env_val, _ = self.exec("echo $PIP_INDEX_URL")
            pip_index = env_val.strip()
        pip_args = ""
        if pip_index:
            from urllib.parse import urlparse
            host = urlparse(pip_index).hostname or ""
            pip_args = f"-i {pip_index} --trusted-host {host} "
        try:
            apt_timeout = max(1, int(os.environ.get("OPENCLAW_DOCKER_APT_TIMEOUT", "30")))
        except ValueError:
            apt_timeout = 30
        apt_exec_timeout = min(pip_timeout, max(apt_timeout + 30, 60))

        # Check if python3 is available
        exit_code, _, _ = self.exec("which python3")
        if exit_code != 0:
            logger.debug("Installing python3 in container...")
            try:
                self.exec(
                    f"timeout {apt_timeout}s bash -c 'apt-get update -qq && "
                    "apt-get install -y -qq python3 python3-pip python3-venv 2>/dev/null' || true",
                    user="root", timeout=apt_exec_timeout,
                )
            except subprocess.TimeoutExpired:
                logger.warning("Timed out installing python3 via apt; continuing with available runtime")

        # Ensure pip is available. The OpenClaw image commonly has python3 but
        # not pip; prefer distro/stdlib installation before fetching get-pip.py.
        exit_code, _, _ = self.exec("python3 -m pip --version")
        if exit_code != 0:
            logger.debug("Installing pip via ensurepip/apt in container...")
            self.exec("python3 -m ensurepip --upgrade >/dev/null 2>&1 || true",
                      user="root", timeout=min(pip_timeout, 180))

        exit_code, _, _ = self.exec("python3 -m pip --version")
        if exit_code != 0:
            logger.debug("Installing pip via apt in container...")
            try:
                self.exec(
                    f"timeout {apt_timeout}s bash -c 'apt-get update -qq && "
                    "apt-get install -y -qq python3-pip python3-venv 2>/dev/null' || true",
                    user="root", timeout=apt_exec_timeout,
                )
            except subprocess.TimeoutExpired:
                logger.warning("Timed out installing pip via apt; falling back to get-pip")

        exit_code, _, _ = self.exec("python3 -m pip --version")
        if exit_code != 0:
            pip_wheel = _find_host_pip_wheel()
            if pip_wheel is not None:
                logger.debug("Installing pip from host bundled wheel: %s", pip_wheel)
                try:
                    container_wheel = f"/tmp/{pip_wheel.name}"
                    self.copy_into(pip_wheel, container_wheel, user="root")
                    self.exec(
                        f"PYTHONPATH={shlex.quote(container_wheel)} python3 -m pip install "
                        f"--no-index --force-reinstall {shlex.quote(container_wheel)} --break-system-packages",
                        user="root",
                        timeout=60,
                    )
                except (RuntimeError, subprocess.TimeoutExpired) as exc:
                    logger.warning("Failed to install pip from host bundled wheel: %s", exc)

        exit_code, _, _ = self.exec("python3 -m pip --version")
        if exit_code != 0:
            logger.debug("Installing pip with get-pip fallback...")
            self.exec(
                "(curl -fsSL --connect-timeout 20 --max-time 120 "
                "https://bootstrap.pypa.io/get-pip.py -o /tmp/get-pip.py && "
                f"python3 /tmp/get-pip.py --break-system-packages {pip_args}&& "
                "rm -f /tmp/get-pip.py)",
                user="root", timeout=pip_timeout
            )

        # Create python and pip3 symlinks if needed
        self.exec("ln -sf /usr/bin/python3 /usr/local/bin/python 2>/dev/null || true", user="root")
        # Ensure pip3 is in PATH (get-pip.py may install to ~/.local/bin)
        self.exec(
            "ln -sf /home/node/.local/bin/pip3 /usr/local/bin/pip3 2>/dev/null || "
            "ln -sf /usr/local/bin/pip3 /usr/local/bin/pip3 2>/dev/null || true",
            user="root"
        )
        # Make pip3 use --break-system-packages by default
        self.exec(
            "pip3 config set global.break-system-packages true 2>/dev/null || "
            "python3 -m pip config set global.break-system-packages true 2>/dev/null || true",
            user="root"
        )

    def _diagnose_mcp_after_init(self, fixture_dir: Path) -> None:
        """Log diagnostic information about MCP registration after init.sh."""
        health_candidates = _health_check_candidates(fixture_dir)
        if not health_candidates:
            health_candidates = [(9130, "/pasb/health")]
        for port, endpoint in health_candidates:
            exit_code, stdout, _ = self.exec(
                f"curl -sf http://localhost:{port}{endpoint} 2>&1 || echo 'MOCK_SERVICE_NOT_RUNNING'"
            )
            if "MOCK_SERVICE_NOT_RUNNING" in stdout:
                logger.warning("[%s] Mock service not running on port %s%s", self.task_id, port, endpoint)
            else:
                logger.debug("[%s] Mock service is running on port %s%s: %s",
                             self.task_id, port, endpoint, stdout[:200])

        # Check openclaw.json for MCP config (faster than openclaw mcp list)
        exit_code, stdout, _ = self.exec("cat /home/node/.openclaw/openclaw.json 2>/dev/null")
        if exit_code == 0 and stdout.strip():
            try:
                config = json.loads(stdout)
                mcp_servers = config.get("mcp", {}).get("servers", {})
                if not mcp_servers:
                    mcp_servers = config.get("mcpServers", {})
                if mcp_servers:
                    logger.debug("[%s] MCP servers in config after init: %s",
                                self.task_id, ", ".join(mcp_servers.keys()))
                    for name, srv in mcp_servers.items():
                        logger.debug("[%s]   %s: %s", self.task_id, name, json.dumps(srv)[:200])
                else:
                    logger.warning("[%s] No MCP servers found in openclaw.json after init.sh", self.task_id)
            except json.JSONDecodeError:
                logger.warning("[%s] openclaw.json is not valid JSON after init", self.task_id)
        else:
            logger.warning("[%s] Could not read openclaw.json after init", self.task_id)

        # Check openclaw mcp list (with longer timeout, non-fatal)
        try:
            exit_code, stdout, stderr = self.exec("openclaw mcp list 2>&1", timeout=30)
            logger.debug("[%s] openclaw mcp list after init: exit=%d stdout=%s",
                        self.task_id, exit_code, stdout[:500])
        except Exception as e:
            logger.warning("[%s] openclaw mcp list timed out or failed: %s", self.task_id, e)

    def _patch_init_sh_mcp_syntax(self) -> None:
        """Patch /opt/init.sh to fix `openclaw mcp set --command` syntax.

        Older init.sh files use: openclaw mcp set <name> --command X --args Y
        The correct syntax is:    openclaw mcp set <name> '{"command":"X","args":["Y"]}'
        Writes a Python patch script into the container and runs it.
        """
        patch_lines = [
            "import re, json",
            "with open('/opt/init.sh','r') as f: c=f.read()",
            "def fix(m):",
            "  n=m.group('n'); cmd=m.group('c'); a=m.group('a')",
            "  args=[x.strip().strip('\"').strip(\"'\") for x in a.split() if x.strip()]",
            "  cfg=json.dumps({'command':cmd,'args':args})",
            "  return f\"openclaw mcp set {n} '{cfg}'\"",
            "p=r'openclaw\\s+mcp\\s+set\\s+(?P<n>\\S+)\\s+--command\\s+(?P<c>\\S+)\\s+--args\\s+(?P<a>.+?)(?:\\s*2>/dev/null|\\s*\\|\\||\\s*&&|\\s*;|$)'",
            "nc=re.sub(p,fix,c)",
            "if nc!=c:",
            "  with open('/opt/init.sh','w') as f: f.write(nc)",
            "  print('Patched init.sh MCP syntax')",
        ]
        patch_script = "\n".join(patch_lines)
        self.exec(f"cat > /tmp/patch_mcp.py << 'PATCHEOF'\n{patch_script}\nPATCHEOF", user="root")
        exit_code, stdout, stderr = self.exec("python3 /tmp/patch_mcp.py", user="root", timeout=15)
        if exit_code == 0 and "Patched" in stdout:
            logger.debug("Patched init.sh MCP set syntax for task %s", self.task_id)
        else:
            logger.debug("No MCP syntax patch needed for task %s", self.task_id)

    def deploy_fixture(self, fixture_dir: Path, workspace_path: str | None = None) -> None:
        """Deploy task fixture files into the container.

        Fixture directory structure:
          fixture/
            ├── init.sh          -> /opt/init.sh (run after copy)
            ├── workspace/       -> /home/node/workspace/
            ├── mcp/             -> /opt/mcp/
            ├── mock_service/    -> /opt/mock_service/
            └── local_files/     -> /opt/local_files/
        """
        if not fixture_dir.exists():
            logger.warning("Fixture directory does not exist: %s", fixture_dir)
            return

        self.prepare_workspace_paths(workspace_path)

        # Copy workspace files to /home/node/workspace
        workspace_dir = fixture_dir / "workspace"
        if workspace_dir.exists():
            self.copy_into(workspace_dir, DEFAULT_WORKSPACE_PATH)

        # Copy MCP service files to /opt/mcp
        mcp_dir = fixture_dir / "mcp"
        if mcp_dir.exists():
            self.copy_into(mcp_dir, "/opt/mcp")

        # Copy mock service files to /opt/mock_service
        mock_dir = fixture_dir / "mock_service"
        if mock_dir.exists():
            self.copy_into(mock_dir, "/opt/mock_service")

        # Copy local files to /opt/local_files
        local_files_dir = fixture_dir / "local_files"
        if local_files_dir.exists():
            self.copy_into(local_files_dir, "/opt/local_files")

        # Ensure workspace is writable by node user
        self.exec(f"chown -R node:node {shlex.quote(DEFAULT_WORKSPACE_PATH)}", user="root")
        self.exec(f"chmod -R u+rw {shlex.quote(DEFAULT_WORKSPACE_PATH)}", user="root")

        # Copy and run init.sh (as root since it may need pip install, symlink creation, etc.)
        init_script = fixture_dir / "init.sh"
        if init_script.exists():
            init_source = init_script
            patched_init_path: Path | None = None
            try:
                init_content = init_script.read_text(encoding="utf-8")
                patched_init = _patch_init_script_for_docker(init_content)
                if patched_init != init_content:
                    with tempfile.NamedTemporaryFile("w", encoding="utf-8", delete=False) as tmp:
                        tmp.write(patched_init)
                        patched_init_path = Path(tmp.name)
                    init_source = patched_init_path
            except OSError as exc:
                logger.warning("[%s] Could not patch init.sh before copy: %s", self.task_id, exc)

            try:
                self.copy_into(init_source, "/opt/init.sh")
            finally:
                if patched_init_path is not None:
                    patched_init_path.unlink(missing_ok=True)
            self.exec("chmod +x /opt/init.sh", user="root")
            # Fix ownership of /opt directories so init.sh can write
            self.exec("chown -R node:node /opt/mcp /opt/mock_service /opt/local_files", user="root")
            # Ensure Python and pip are available in the container
            self._ensure_python()
            # Patch init.sh: fix `openclaw mcp set <name> --command X --args Y` to JSON format
            # The correct syntax is: openclaw mcp set <name> '{"command":"X","args":["Y"]}'
            self._patch_init_sh_mcp_syntax()
            logger.info("[%s] Running init.sh...", self.task_id)
            # Run init.sh as root (needed for pip install, symlink creation, etc.)
            # but set HOME=/home/node so that `openclaw mcp set` writes to the
            # node user's config directory, not /root/.openclaw/
            exit_code, stdout, stderr = self.exec(
                "HOME=/home/node bash /opt/init.sh", user="root", timeout=self.init_timeout
            )
            self.exec("chown -R node:node /home/node/.openclaw 2>/dev/null || true", user="root")
            if exit_code != 0:
                logger.error("init.sh failed for task %s:\nstdout: %s\nstderr: %s",
                             self.task_id, stdout[:500], stderr[:500])
            else:
                logger.info("[%s] init.sh completed", self.task_id)

            # Diagnose MCP registration after init.sh
            self._diagnose_mcp_after_init(fixture_dir)

    def _agent_directory_candidates(self, agent_id: str) -> list[str]:
        """Return plausible OpenClaw agent directories for the requested agent ID."""
        base = "/home/node/.openclaw/agents"
        candidates = [f"{base}/{agent_id}"]
        lower_agent_id = agent_id.lower()
        if lower_agent_id != agent_id:
            candidates.append(f"{base}/{lower_agent_id}")

        exit_code, stdout, _ = self.exec(f"ls -1 {base} 2>/dev/null")
        if exit_code == 0 and stdout.strip():
            normalized_agent_id = re.sub(r"[^a-z0-9]+", "-", agent_id.lower()).strip("-")
            for name in stdout.strip().splitlines():
                name = name.strip()
                if not name:
                    continue
                normalized_name = re.sub(r"[^a-z0-9]+", "-", name.lower()).strip("-")
                if normalized_name == normalized_agent_id:
                    candidates.append(f"{base}/{name}")

        unique: list[str] = []
        seen: set[str] = set()
        for candidate in candidates:
            if candidate not in seen:
                seen.add(candidate)
                unique.append(candidate)
        return unique

    def _session_files(self, agent_id: str, newest_first: bool = True) -> list[str]:
        """Find session JSONL files for an agent across OpenClaw directory variants."""
        files: list[str] = []
        for agent_dir in self._agent_directory_candidates(agent_id):
            quoted_agent_dir = shlex.quote(agent_dir)
            exit_code, stdout, _ = self.exec(f"ls -t {quoted_agent_dir}/sessions/*.jsonl 2>/dev/null")
            if exit_code == 0 and stdout.strip():
                files.extend(f.strip() for f in stdout.strip().splitlines() if f.strip())
                continue

            exit_code, stdout, _ = self.exec(
                f"find {quoted_agent_dir} -name '*.jsonl' -type f 2>/dev/null | head -1"
            )
            if exit_code == 0 and stdout.strip():
                files.extend(f.strip() for f in stdout.strip().splitlines() if f.strip())

        unique_files: list[str] = []
        seen: set[str] = set()
        for filepath in files:
            if filepath not in seen:
                seen.add(filepath)
                unique_files.append(filepath)
        if not newest_first:
            unique_files.reverse()
        return unique_files

    def get_transcript(self, agent_id: str) -> list[dict] | None:
        """Read the agent's session transcript from the container.

        Looks for JSONL session files in /home/node/.openclaw/agents/<agent_id>/sessions/.
        OpenClaw may normalize agent directory names (for example, lower-casing
        bench-Example-Model-1 to bench-example-model-1), so discovery follows matching agent
        directories instead of assuming the requested ID is the on-disk name.
        """
        session_files = self._session_files(agent_id)
        if not session_files:
            logger.warning("No transcript found for agent %s in task %s", agent_id, self.task_id)
            return None
        transcript_file = session_files[0]

        # Read the transcript file
        exit_code, stdout, stderr = self.exec(f"cat {shlex.quote(transcript_file)}")
        if exit_code != 0:
            logger.error("Failed to read transcript: %s", stderr)
            return None

        transcript = []
        for line in stdout.strip().split("\n"):
            line = line.strip()
            if line:
                try:
                    transcript.append(json.loads(line))
                except json.JSONDecodeError:
                    logger.warning("Skipping invalid JSON line in transcript")

        return transcript if transcript else None

    def get_last_assistant_text(self, agent_id: str) -> str:
        """Extract the last assistant text from the latest session JSONL.

        Used in multi-turn mode to get the agent's response after each turn.
        Returns empty string if no assistant text found.
        """
        session_files = self._session_files(agent_id)
        if not session_files:
            return ""
        latest_file = session_files[0]
        exit_code, stdout, _ = self.exec(f"cat {shlex.quote(latest_file)}")
        if exit_code != 0:
            return ""

        last_text = ""
        for line in stdout.strip().split("\n"):
            line = line.strip()
            if not line:
                continue
            try:
                entry = json.loads(line)
            except json.JSONDecodeError:
                continue
            if entry.get("type") == "message":
                msg = entry.get("message", {})
                if msg.get("role") == "assistant":
                    content = msg.get("content", [])
                    if isinstance(content, list):
                        for item in reversed(content):
                            if item.get("type") == "text" and item.get("text"):
                                last_text = item["text"]
                                break
                    elif isinstance(content, str):
                        last_text = content
        return last_text

    def get_all_session_transcripts(self, agent_id: str) -> list[list[dict]]:
        """Read ALL session JSONL files for an agent, sorted chronologically.

        In multi-turn mode, each turn creates a new session file. This method
        returns all of them in chronological order for merged transcript.
        """
        files = self._session_files(agent_id, newest_first=False)
        if not files:
            return []

        all_transcripts = []
        for filepath in files:
            exit_code, stdout, _ = self.exec(f"cat {shlex.quote(filepath)}")
            if exit_code != 0:
                continue
            transcript = []
            for line in stdout.strip().split("\n"):
                line = line.strip()
                if line:
                    try:
                        transcript.append(json.loads(line))
                    except json.JSONDecodeError:
                        pass
            if transcript:
                all_transcripts.append(transcript)
        return all_transcripts

    def get_workspace(self, local_dest: Path) -> None:
        """Copy the workspace directory out of the container for grading."""
        self.copy_out("/home/node/workspace", local_dest)

    def stop(self) -> None:
        """Stop and remove the container."""
        if not self._started:
            return

        try:
            _run_docker(["stop", "-t", "5", self.container_name], timeout=30)
        except Exception as e:
            logger.warning("Failed to stop container %s: %s", self.container_name, e)

        try:
            _run_docker(["rm", "-f", self.container_name], timeout=30)
        except Exception as e:
            logger.warning("Failed to remove container %s: %s", self.container_name, e)

        # Clean up docker home
        if self.docker_home.exists():
            try:
                shutil.rmtree(self.docker_home, ignore_errors=True)
            except Exception as e:
                logger.warning("Failed to clean up docker home %s: %s", self.docker_home, e)

        self._started = False
        logger.debug("Container stopped and removed: %s", self.container_name)


def cleanup_stale_containers() -> int:
    """Remove all containers with the openclaw-safety-bench label."""
    result = _run_docker(["ps", "-aq", "--filter", f"label={CONTAINER_LABEL}"])
    container_ids = result.stdout.strip().split("\n") if result.stdout.strip() else []

    if not container_ids:
        return 0

    for cid in container_ids:
        cid = cid.strip()
        if cid:
            try:
                _run_docker(["rm", "-f", cid], timeout=30)
                logger.debug("Removed stale container: %s", cid[:12])
            except Exception as e:
                logger.warning("Failed to remove container %s: %s", cid[:12], e)

    return len(container_ids)


def check_docker_available() -> bool:
    """Check if Docker is available and running."""
    try:
        result = _run_docker(["info"], timeout=10)
        return result.returncode == 0
    except (subprocess.TimeoutExpired, FileNotFoundError):
        return False


def pull_image(image: str = DEFAULT_IMAGE) -> bool:
    """Pull the Docker image if not available locally."""
    # Check if image exists locally
    result = _run_docker(["image", "inspect", image], timeout=10)
    if result.returncode == 0:
        logger.debug("Image %s already available locally", image)
        return True

    logger.info("Pulling image %s...", image)
    try:
        _run_docker_check(["pull", image], timeout=600)
        return True
    except Exception as e:
        logger.error("Failed to pull image %s: %s", image, e)
        return False
