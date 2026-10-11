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

"""Lifecycle management for the simulated User Agent Server.

Starts the simulated_user FastAPI server as a subprocess and waits for
it to become healthy. Used by benchmark.py to auto-manage the server
when user_agent_server mode tasks are present.
"""

import logging
import os
import subprocess
import sys
import time
from pathlib import Path

import httpx

logger = logging.getLogger(__name__)

_HEALTH_CHECK_TIMEOUT = 30
_HEALTH_CHECK_INTERVAL = 1.0


def start_user_agent_server(
    port: int = 9090,
    model: str | None = None,
    base_url: str | None = None,
    api_key: str | None = None,
) -> subprocess.Popen:
    """Start the simulated user agent server as a subprocess.

    Args:
        port: Port for the server to listen on.
        model: LLM model ID for the simulated user.
        base_url: LLM API base URL.
        api_key: LLM API key.

    Returns:
        The subprocess.Popen handle.

    Raises:
        RuntimeError: If the server fails to start or health check times out.
    """
    env = os.environ.copy()
    if model:
        env["USER_AGENT_MODEL_ID"] = model
    if base_url:
        env["USER_AGENT_BASE_URL"] = base_url
    if api_key:
        env["USER_AGENT_API_KEY"] = api_key

    server_dir = Path(__file__).parent / "simulated_user"
    log_file = Path("/tmp/user_agent_server.log")

    logger.info("Starting User Agent Server on port %d...", port)

    with open(log_file, "w") as lf:
        proc = subprocess.Popen(
            [
                sys.executable, "-m", "simulated_user",
                "--host", "0.0.0.0",
                "--port", str(port),
            ],
            cwd=str(Path(__file__).parent),
            env=env,
            stdout=lf,
            stderr=subprocess.STDOUT,
        )

    if not _wait_for_health(port):
        _, stderr = proc.communicate(timeout=5)
        log_content = log_file.read_text()[:1000] if log_file.exists() else "(no log)"
        proc.kill()
        raise RuntimeError(
            f"User Agent Server failed to start on port {port}.\n"
            f"Log: {log_content}"
        )

    logger.info("User Agent Server is ready on port %d (pid=%d)", port, proc.pid)
    return proc


def stop_user_agent_server(proc: subprocess.Popen) -> None:
    """Gracefully stop the user agent server subprocess."""
    if proc.poll() is not None:
        logger.debug("User Agent Server already exited (code=%d)", proc.returncode)
        return

    logger.info("Stopping User Agent Server (pid=%d)...", proc.pid)
    proc.terminate()
    try:
        proc.wait(timeout=5)
    except subprocess.TimeoutExpired:
        logger.warning("User Agent Server did not terminate gracefully, killing...")
        proc.kill()
        proc.wait(timeout=3)

    logger.info("User Agent Server stopped")


def _wait_for_health(port: int) -> bool:
    """Wait for the server's /health endpoint to respond."""
    url = f"http://localhost:{port}/health"
    start = time.time()

    while time.time() - start < _HEALTH_CHECK_TIMEOUT:
        try:
            resp = httpx.get(url, timeout=2.0)
            if resp.status_code == 200:
                logger.debug("User Agent Server health check passed (%.1fs)", time.time() - start)
                return True
        except (httpx.ConnectError, httpx.TimeoutException):
            pass
        time.sleep(_HEALTH_CHECK_INTERVAL)

    logger.error("User Agent Server health check timed out after %ds", _HEALTH_CHECK_TIMEOUT)
    return False
