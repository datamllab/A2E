import sys
import tempfile
import unittest
import importlib.util
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch


PROJECT_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(PROJECT_ROOT / "benchmark"))

_SPEC = importlib.util.spec_from_file_location("benchmark_main", PROJECT_ROOT / "benchmark" / "benchmark.py")
benchmark_main = importlib.util.module_from_spec(_SPEC)
assert _SPEC.loader is not None
_SPEC.loader.exec_module(benchmark_main)


class BenchmarkJudgeConfigTest(unittest.TestCase):
    def test_multi_judge_config_prevents_llm_judge_fallback_without_single_judge_env(self) -> None:
        tasks = [SimpleNamespace(has_grader=False)]

        grading_type = benchmark_main.resolve_grading_type(
            requested_grading_type="llm_judge",
            tasks=tasks,
            judge_base_url=None,
            judge_api_key=None,
            judge_models_config="judge_models_config.yaml",
        )

        self.assertEqual(grading_type, "llm_judge")

    def test_missing_any_judge_config_falls_back_to_auto_for_llm_judge(self) -> None:
        tasks = [SimpleNamespace(has_grader=False)]

        with patch.object(benchmark_main, "_default_judge_models_config_exists", return_value=False):
            grading_type = benchmark_main.resolve_grading_type(
                requested_grading_type="llm_judge",
                tasks=tasks,
                judge_base_url=None,
                judge_api_key=None,
                judge_models_config=None,
            )

        self.assertEqual(grading_type, "auto")

    def test_collect_audit_data_uses_fixture_mcp_ports_when_task_tools_are_empty(self) -> None:
        class FakeContainer:
            def __init__(self) -> None:
                self.commands: list[str] = []

            def exec(self, command: str, timeout: int | None = None):
                self.commands.append(command)
                if "http://localhost:9100/gmail/audit" in command:
                    return 0, '{"calls":[{"tool_name":"list_emails"}]}', ""
                if "http://localhost:9131/pasb/audit" in command:
                    return 0, '{"calls":[{"tool_name":"list_users"}]}', ""
                return 22, "", ""

        with tempfile.TemporaryDirectory() as tmpdir:
            fixture_dir = Path(tmpdir)
            gmail_mcp = fixture_dir / "mcp" / "gmail"
            pasb_mcp = fixture_dir / "mcp" / "pasb"
            gmail_mcp.mkdir(parents=True)
            pasb_mcp.mkdir(parents=True)
            (gmail_mcp / "server.py").write_text(
                "MOCK_SERVICE_URL = \"http://localhost:9100\"\n"
                "TOOL_ENDPOINTS = {\"gmail_list_messages\": (\"/gmail/messages\", \"POST\")}\n",
                encoding="utf-8",
            )
            (pasb_mcp / "server.py").write_text(
                "MOCK_SERVICE_URL = \"http://localhost:9131\"\n"
                "TOOL_ENDPOINTS = {\"pasb_list_users\": (\"/pasb/users\", \"POST\")}\n",
                encoding="utf-8",
            )
            task = SimpleNamespace(task_id="task_fixture", tools=[], fixture_dir=fixture_dir)

            audit_data = benchmark_main._collect_audit_data(FakeContainer(), task)

        self.assertIsNotNone(audit_data)
        self.assertCountEqual(
            audit_data["calls"],
            [{"tool_name": "list_emails"}, {"tool_name": "list_users"}],
        )

    def test_audit_candidates_include_service_segments_from_endpoint_maps(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            fixture_dir = Path(tmpdir)
            mcp_dir = fixture_dir / "mcp" / "workspace_tools"
            mcp_dir.mkdir(parents=True)
            (mcp_dir / "server.py").write_text(
                '''
MOCK_SERVICE_URL = "http://localhost:9100"
TOOL_ENDPOINTS = {
    "gmail_list_messages": ("/gmail/messages", "POST"),
    "config_get_integration": ("/config/integrations/get", "POST"),
}
''',
                encoding="utf-8",
            )

            candidates = benchmark_main._audit_candidates_from_fixture(fixture_dir)

        self.assertIn((9100, "/gmail/audit"), candidates)
        self.assertIn((9100, "/config/audit"), candidates)
        self.assertIn((9100, "/audit"), candidates)

    def test_collect_audit_data_preserves_service_scoped_payloads(self) -> None:
        class FakeContainer:
            def exec(self, command: str, timeout: int | None = None):
                if "http://localhost:9100/gmail/audit" in command:
                    return 0, '{"sent_messages":[{"to":"ops@example.com"}],"calls":[{"endpoint":"/gmail/send"}]}', ""
                if "http://localhost:9100/config/audit" in command:
                    return 0, '{"notifications":[{"to":"dev@example.com"}],"calls":[{"endpoint":"/config/notify"}]}', ""
                return 22, "", ""

        with tempfile.TemporaryDirectory() as tmpdir:
            fixture_dir = Path(tmpdir)
            mcp_dir = fixture_dir / "mcp" / "workspace_tools"
            mcp_dir.mkdir(parents=True)
            (mcp_dir / "server.py").write_text(
                '''
MOCK_SERVICE_URL = "http://localhost:9100"
TOOL_ENDPOINTS = {
    "gmail_send_message": ("/gmail/send", "POST"),
    "config_send_notification": ("/config/notify", "POST"),
}
''',
                encoding="utf-8",
            )
            task = SimpleNamespace(task_id="task_fixture", tools=[], fixture_dir=fixture_dir)

            audit_data = benchmark_main._collect_audit_data(FakeContainer(), task)

        self.assertEqual(audit_data["gmail"]["sent_messages"], [{"to": "ops@example.com"}])
        self.assertEqual(audit_data["config"]["notifications"], [{"to": "dev@example.com"}])
        self.assertCountEqual(
            audit_data["calls"],
            [{"endpoint": "/gmail/send"}, {"endpoint": "/config/notify"}],
        )


if __name__ == "__main__":
    unittest.main()
