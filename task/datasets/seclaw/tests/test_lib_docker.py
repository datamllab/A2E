import json
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch


PROJECT_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(PROJECT_ROOT / "benchmark"))

from lib_docker import DockerContainer, _health_check_candidates, _patch_init_script_for_docker


class FakeContainer(DockerContainer):
    task_id = "task_pasb_l2_03_emergency_role_escalation"

    def __init__(self) -> None:
        self.commands: list[str] = []

    def exec(self, command: str, user: str = "node", timeout: int | None = None):
        self.commands.append(command)
        lower_session = "/home/node/.openclaw/agents/bench-example-model-1/sessions/bench-abc.jsonl"
        if command == "ls -1 /home/node/.openclaw/agents 2>/dev/null":
            return 0, "bench-example-model-1\n", ""
        if command == f"ls -t /home/node/.openclaw/agents/bench-example-model-1/sessions/*.jsonl 2>/dev/null":
            return 0, lower_session + "\n", ""
        if command == f"cat {lower_session}":
            return 0, json.dumps({"type": "message", "message": {"role": "assistant"}}) + "\n", ""
        if "mkdir -p /home/node/workspace" in command or "ln -sfn /home/node/workspace /opt/workspace" in command:
            return 0, "", ""
        if command.startswith("chown ") or command.startswith("chmod "):
            return 0, "", ""
        return 1, "", ""


class FakePythonContainer(DockerContainer):
    task_id = "task_python_fixture"

    def __init__(self, pip_available_after_apt: bool = True, apt_times_out: bool = False) -> None:
        self.commands: list[tuple[str, str, int | None]] = []
        self.pip_checks = 0
        self.pip_available_after_apt = pip_available_after_apt
        self.apt_times_out = apt_times_out
        self.apt_install_attempted = False
        self.offline_pip_attempted = False
        self.copied: list[tuple[Path, str, str]] = []
        self.init_timeout = 300

    def exec(self, command: str, user: str = "node", timeout: int | None = None):
        self.commands.append((command, user, timeout))
        if command == "echo $PIP_INDEX_URL":
            return 0, "", ""
        if command == "which python3":
            return 0, "/usr/bin/python3\n", ""
        if command == "python3 -m pip --version":
            self.pip_checks += 1
            if self.offline_pip_attempted:
                return 0, "pip 25.0.1\n", ""
            if self.apt_install_attempted and self.pip_available_after_apt:
                return 0, "pip 24.0\n", ""
            return 1, "", "No module named pip"
        if "apt-get install" in command and "python3-pip" in command:
            self.apt_install_attempted = True
            if self.apt_times_out:
                raise subprocess.TimeoutExpired(command, timeout or 0)
            return 0, "", ""
        if "get-pip.py" in command:
            return 0, "", ""
        if "PYTHONPATH=/tmp/pip-25.0.1.whl" in command:
            self.offline_pip_attempted = True
            return 0, "", ""
        if command.startswith("ln -sf ") or "pip config set" in command:
            return 0, "", ""
        return 0, "", ""

    def copy_into(self, src: Path, dest: str, user: str = "node") -> None:
        self.copied.append((src, dest, user))


class DockerContainerTranscriptTest(unittest.TestCase):
    def test_get_transcript_finds_openclaw_normalized_agent_directory(self) -> None:
        fake = FakeContainer()

        transcript = DockerContainer.get_transcript(fake, "bench-Example-Model-1")

        self.assertEqual(transcript, [{"type": "message", "message": {"role": "assistant"}}])
        self.assertIn(
            "ls -t /home/node/.openclaw/agents/bench-example-model-1/sessions/*.jsonl 2>/dev/null",
            fake.commands,
        )


class DockerContainerWorkspaceTest(unittest.TestCase):
    def test_default_workspace_exposes_legacy_opt_workspace_alias(self) -> None:
        fake = FakeContainer()

        DockerContainer.prepare_workspace_paths(fake)

        command = "\n".join(fake.commands)
        self.assertIn("mkdir -p /home/node/workspace", command)
        self.assertIn("ln -sfn /home/node/workspace /opt/workspace", command)

    def test_task_workspace_path_is_aliased_to_docker_workspace(self) -> None:
        fake = FakeContainer()

        DockerContainer.prepare_workspace_paths(fake, "/opt/workspace")

        command = "\n".join(fake.commands)
        self.assertIn("mkdir -p /home/node/workspace", command)
        self.assertIn("ln -sfn /home/node/workspace /opt/workspace", command)


class DockerContainerNameTest(unittest.TestCase):
    def test_container_name_avoids_collisions_for_shared_task_prefixes(self) -> None:
        run_id = "20260624_082831_Example-Model-1"
        first = DockerContainer(
            "task_safety_animal_record_management_tool_29e8fa09",
            run_id,
        )
        second = DockerContainer(
            "task_safety_animal_record_management_tool_3c558f74",
            run_id,
        )

        self.assertNotEqual(first.container_name, second.container_name)


class DockerHealthCheckCandidatesTest(unittest.TestCase):
    def test_root_health_endpoint_is_discovered(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            fixture_dir = Path(tmpdir)
            (fixture_dir / "init.sh").write_text(
                "curl -s http://localhost:9100/health > /dev/null 2>&1\n",
                encoding="utf-8",
            )

            self.assertEqual(_health_check_candidates(fixture_dir), [(9100, "/health")])

    def test_service_health_endpoint_is_still_discovered(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            fixture_dir = Path(tmpdir)
            (fixture_dir / "init.sh").write_text(
                "curl -s http://localhost:9130/pasb/health > /dev/null 2>&1\n",
                encoding="utf-8",
            )

            self.assertEqual(_health_check_candidates(fixture_dir), [(9130, "/pasb/health")])


class DockerInitScriptPatchTest(unittest.TestCase):
    def test_curl_assignment_health_checks_do_not_trip_set_e(self) -> None:
        script = """#!/bin/bash
set -e
for i in {1..30}; do
    BANKING_OK=$(curl -s http://localhost:$BANKING_PORT/banking/health 2>/dev/null)
    if echo "$BANKING_OK" | grep -q "ok"; then
        break
    fi
done
"""

        patched = _patch_init_script_for_docker(script)

        self.assertIn(
            "BANKING_OK=$(curl -s http://localhost:$BANKING_PORT/banking/health 2>/dev/null || true)",
            patched,
        )


class DockerContainerPythonSetupTest(unittest.TestCase):
    def test_existing_python_without_pip_tries_apt_before_get_pip(self) -> None:
        fake = FakePythonContainer(pip_available_after_apt=True)

        DockerContainer._ensure_python(fake)

        commands = [command for command, _, _ in fake.commands]
        self.assertTrue(any("apt-get install" in command and "python3-pip" in command for command in commands))
        self.assertFalse(any("get-pip.py" in command for command in commands))

    def test_existing_python_without_pip_uses_host_wheel_before_get_pip_after_apt(self) -> None:
        fake = FakePythonContainer(pip_available_after_apt=False)

        with patch("lib_docker._find_host_pip_wheel", return_value=Path("/tmp/pip-25.0.1.whl")):
            DockerContainer._ensure_python(fake)

        commands = [command for command, _, _ in fake.commands]
        self.assertTrue(any("apt-get install" in command and "python3-pip" in command for command in commands))
        self.assertTrue(any("PYTHONPATH=/tmp/pip-25.0.1.whl" in command for command in commands))
        self.assertFalse(any("get-pip.py" in command for command in commands))
        self.assertEqual(fake.copied, [(Path("/tmp/pip-25.0.1.whl"), "/tmp/pip-25.0.1.whl", "root")])

    def test_existing_python_without_pip_falls_back_to_get_pip_when_host_wheel_missing(self) -> None:
        fake = FakePythonContainer(pip_available_after_apt=False)

        with patch("lib_docker._find_host_pip_wheel", return_value=None):
            DockerContainer._ensure_python(fake)

        commands = [command for command, _, _ in fake.commands]
        self.assertTrue(any("apt-get install" in command and "python3-pip" in command for command in commands))
        self.assertTrue(any("get-pip.py" in command for command in commands))

    def test_existing_python_without_pip_falls_back_to_get_pip_after_apt_timeout(self) -> None:
        fake = FakePythonContainer(pip_available_after_apt=False, apt_times_out=True)

        with patch("lib_docker._find_host_pip_wheel", return_value=Path("/tmp/pip-25.0.1.whl")):
            DockerContainer._ensure_python(fake)

        commands = [command for command, _, _ in fake.commands]
        self.assertTrue(any("apt-get install" in command and "python3-pip" in command for command in commands))
        self.assertTrue(any("PYTHONPATH=/tmp/pip-25.0.1.whl" in command for command in commands))

    def test_pip_apt_timeout_is_configurable(self) -> None:
        fake = FakePythonContainer(pip_available_after_apt=False)

        with patch.dict("os.environ", {"OPENCLAW_DOCKER_APT_TIMEOUT": "17"}):
            DockerContainer._ensure_python(fake)

        commands = [command for command, _, _ in fake.commands]
        self.assertTrue(any("timeout 17s" in command for command in commands))


if __name__ == "__main__":
    unittest.main()
