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

"""Task model and loader for the benchmark framework.

Loads tasks from the existing tasks/openclaw/ directory structure:
  tasks/openclaw/task_{category}_{desc}_{uuid}/v{N}/
    ├── task.yaml          # name, category, prompt, tools, judge_rubric
    ├── metadata.yaml      # source, tags, difficulty, dimensions
    ├── grader.py          # grade(transcript, workspace_path, audit_data) -> dict
    └── fixture/           # init.sh, workspace/, mcp/, mock_service/
"""

import importlib.util
import json
import re
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

import yaml


VERSION_DIR_RE = re.compile(r"^v(\d+)$")


@dataclass
class ToolDef:
    """MCP tool definition from task.yaml."""

    name: str
    description: str
    endpoint: str
    schema: dict[str, Any] = field(default_factory=dict)


@dataclass
class JudgeRubricCriterion:
    """A single criterion in the judge rubric."""

    description: str
    weight: float
    rubric: list[dict[str, Any]] = field(default_factory=list)


@dataclass
class JudgeRubric:
    """LLM judge configuration from task.yaml."""

    model: str
    api_base: str
    criteria: dict[str, JudgeRubricCriterion] = field(default_factory=dict)


@dataclass
class DialogueStep:
    """A single round in a scripted dialogue."""

    round: int          # 1-indexed; round 1 is the initial task prompt
    message: str


@dataclass
class StopCondition:
    """Condition for early termination of multi-turn dialogue."""

    type: str           # "keyword_match" or "tool_call_match"
    keywords: list[str] = field(default_factory=list)
    tool_names: list[str] = field(default_factory=list)
    min_round: int = 1


@dataclass
class UserAgentConfig:
    """Configuration for multi-turn simulated user.

    Supported modes:
    - "scripted": Follows a fixed dialogue_script with round/message pairs.
    - "querylist": Sends messages from a simple string list in order.
    - "adaptive": Uses an LLM to dynamically generate follow-up messages.
    - "user_agent_server": Uses an LLM with a server-style prompt (compatible
      with claw_demo's simulated_user_server API), either in-process or via HTTP.
    """

    enabled: bool = False
    mode: str = "scripted"   # "scripted", "adaptive", "querylist", "user_agent_server"
    max_rounds: int = 1
    dialogue_script: list[DialogueStep] = field(default_factory=list)
    query_list: list[str] = field(default_factory=list)      # querylist mode: ordered list of messages
    system_prompt: str = ""
    model: str = ""
    api_base: str = ""
    api_key: str = ""        # resolved from env at runtime
    inject_context: bool = False
    stop_conditions: list[StopCondition] = field(default_factory=list)
    server_url: str = ""     # user_agent_server mode: HTTP endpoint for external service
    prompt_file: str = ""    # user_agent_server mode: custom system prompt file path


@dataclass
class Task:
    """A benchmark task loaded from disk."""

    task_id: str
    version: str
    name: str
    category: str
    prompt: str
    task_dir: Path
    tools: list[ToolDef] = field(default_factory=list)
    judge_rubric: JudgeRubric | None = None
    metadata: dict[str, Any] = field(default_factory=dict)
    fixture_dir: Path | None = None
    workspace_path: str = "/home/node/workspace"
    user_agent: UserAgentConfig | None = None
    _grader_module: Any = None

    @property
    def has_fixture(self) -> bool:
        return self.fixture_dir is not None and self.fixture_dir.exists()

    @property
    def has_init_script(self) -> bool:
        return self.fixture_dir is not None and (self.fixture_dir / "init.sh").exists()

    @property
    def has_grader(self) -> bool:
        return (self.task_dir / "grader.py").exists()

    @property
    def has_judge(self) -> bool:
        return self.judge_rubric is not None

    @property
    def is_multi_turn(self) -> bool:
        return self.user_agent is not None and self.user_agent.enabled

    @property
    def grader_path(self) -> Path:
        return self.task_dir / "grader.py"

    def load_grader(self) -> Any:
        """Dynamically load the grader.py module and return it."""
        if self._grader_module is not None:
            return self._grader_module

        if not self.has_grader:
            return None

        spec = importlib.util.spec_from_file_location("grader", str(self.grader_path))
        if spec is None or spec.loader is None:
            return None

        module = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(module)
        self._grader_module = module
        return module


def _format_rs_list(items: list[Any]) -> str:
    """Render list-form reference_solution like ARCA run_batch_init.py."""
    lines = []
    for item in items:
        if isinstance(item, str):
            lines.append(item)
        elif isinstance(item, dict):
            for key, val in item.items():
                lines.append(f"{key}: {val}" if isinstance(val, str) else f"{key}: {val}")
        else:
            lines.append(str(item))
    return "\n".join(lines)


def _format_rs_dict(rs_dict: dict[str, Any]) -> str:
    """Render dict-form reference_solution like ARCA run_batch_init.py."""
    sections = []

    steps = rs_dict.get("steps", [])
    if steps:
        sections.append("Steps:")
        for i, step in enumerate(steps, 1):
            sections.append(f"  {i}. {step}")

    for key in ("safety", "safety_notes"):
        items = rs_dict.get(key, [])
        if items and isinstance(items, list):
            label = key.replace("_", " ").title()
            sections.append(f"{label}:")
            for item in items:
                sections.append(f"  - {item}")

    safety_note = rs_dict.get("safety_note")
    if safety_note and isinstance(safety_note, str):
        sections.append("Safety Note:")
        sections.append(f"  {safety_note}")

    for key in rs_dict:
        if key in ("steps", "safety", "safety_notes", "safety_note"):
            continue
        items = rs_dict.get(key)
        if isinstance(items, list) and items:
            label = key.replace("_", " ").title()
            sections.append(f"{label}:")
            for item in items:
                sections.append(f"  - {item}")
        elif isinstance(items, str) and items:
            label = key.replace("_", " ").title()
            sections.append(f"{label}:")
            sections.append(f"  {items}")

    return "\n".join(sections)


def format_reference_solution(reference_solution: Any) -> str:
    """Normalize metadata.yaml reference_solution using ARCA-compatible text."""
    if reference_solution is None:
        return ""
    if isinstance(reference_solution, str):
        return reference_solution.strip()
    if isinstance(reference_solution, list):
        return _format_rs_list(reference_solution)
    if isinstance(reference_solution, dict):
        return _format_rs_dict(reference_solution)
    return str(reference_solution).strip()


def append_reference_solution(prompt: str, reference_solution: Any) -> str:
    """Append reference_solution to a task prompt with ARCA-compatible wording."""
    formatted_rs = format_reference_solution(reference_solution)
    if not formatted_rs:
        return prompt
    return (
        prompt.rstrip()
        + "\n\n---\nReference Solution (expected correct behavior):\n\n"
        + formatted_rs
    )


def apply_reference_solution(tasks: list[Task]) -> None:
    """Mutate loaded tasks so their prompts include metadata.reference_solution."""
    for task in tasks:
        task.prompt = append_reference_solution(
            task.prompt,
            task.metadata.get("reference_solution"),
        )


def _parse_tools(tools_data: list[dict[str, Any]] | None) -> list[ToolDef]:
    """Parse tool definitions from task.yaml."""
    if not tools_data:
        return []
    result = []
    for t in tools_data:
        result.append(ToolDef(
            name=t.get("name", ""),
            description=t.get("description", ""),
            endpoint=t.get("endpoint", ""),
            schema=t.get("schema", {}),
        ))
    return result


def _parse_judge_rubric(rubric_data: dict[str, Any] | str | None) -> JudgeRubric | None:
    """Parse judge_rubric from task.yaml.

    Handles both dict format (with criteria) and string format (raw prompt text).
    String format rubrics are stored as a single criterion for LLM judge use.
    """
    if not rubric_data:
        return None

    # String format: treat as a raw prompt for the judge
    if isinstance(rubric_data, str):
        return JudgeRubric(
            model="",
            api_base="",
            criteria={
                "rubric_text": JudgeRubricCriterion(
                    description=rubric_data,
                    weight=1.0,
                    rubric=[],
                ),
            },
        )

    criteria = {}
    for name, c in rubric_data.get("criteria", {}).items():
        rubric_items = []
        for item in c.get("rubric", []):
            rubric_items.append(item)
        criteria[name] = JudgeRubricCriterion(
            description=c.get("description", ""),
            weight=c.get("weight", 0.0),
            rubric=rubric_items,
        )

    return JudgeRubric(
        model=rubric_data.get("model", ""),
        api_base=rubric_data.get("api_base", ""),
        criteria=criteria,
    )


def _parse_user_agent(ua_data: dict[str, Any] | None) -> UserAgentConfig | None:
    """Parse user_agent config from task.yaml."""
    if not ua_data or not ua_data.get("enabled", False):
        return None

    script = []
    for step in ua_data.get("dialogue_script", []):
        script.append(DialogueStep(
            round=step["round"],
            message=step["message"],
        ))

    stops = []
    for sc in ua_data.get("stop_conditions", []):
        stops.append(StopCondition(
            type=sc.get("type", "keyword_match"),
            keywords=sc.get("keywords", []),
            tool_names=sc.get("tool_names", []),
            min_round=sc.get("min_round", 1),
        ))

    query_list = ua_data.get("query_list", [])
    mode = ua_data.get("mode", "scripted")

    # For querylist mode, auto-calculate max_rounds if not explicitly set
    max_rounds = ua_data.get("max_rounds", 0)
    if mode == "querylist" and query_list and max_rounds == 0:
        max_rounds = len(query_list) + 1  # +1 for the initial task prompt (round 1)
    elif max_rounds == 0:
        max_rounds = 1

    return UserAgentConfig(
        enabled=True,
        mode=mode,
        max_rounds=max_rounds,
        dialogue_script=script,
        query_list=query_list,
        system_prompt=ua_data.get("system_prompt", ""),
        model=ua_data.get("model", ""),
        api_base=ua_data.get("api_base", ""),
        api_key=ua_data.get("api_key", ""),
        inject_context=ua_data.get("inject_context", False),
        stop_conditions=stops,
        server_url=ua_data.get("server_url", ""),
        prompt_file=ua_data.get("prompt_file", ""),
    )


def _parse_workspace_path(workspace_data: Any) -> str:
    """Parse workspace path from task.yaml.

    Historical OpenClaw tasks use both:
      workspace: /opt/workspace
      workspace:
        path: /opt/workspace
    """
    if isinstance(workspace_data, str) and workspace_data.strip():
        return workspace_data.strip()
    if isinstance(workspace_data, dict):
        path = workspace_data.get("path")
        if isinstance(path, str) and path.strip():
            return path.strip()
    return "/home/node/workspace"


def _parse_version_dir(path: Path) -> int | None:
    """Return the numeric version for a vN directory, or None."""
    match = VERSION_DIR_RE.match(path.name)
    if not match:
        return None
    return int(match.group(1))


def resolve_task_dir(task_dir: Path) -> tuple[Path, str, str]:
    """Resolve a flat or versioned task root to an executable task directory.

    Supported inputs:
    - Flat: tasks/openclaw/task_xxx/task.yaml
    - Version root: tasks/openclaw/task_xxx/vN/task.yaml
    - Version dir: tasks/openclaw/task_xxx/vN

    If both a flat task.yaml and version directories exist, the flat structure
    wins to preserve open_source dataset compatibility.

    Returns:
        (resolved_task_dir, task_id, version)
    """
    if not task_dir.exists():
        raise FileNotFoundError(f"Task directory not found: {task_dir}")

    if (task_dir / "task.yaml").exists():
        version_num = _parse_version_dir(task_dir)
        if version_num is not None and task_dir.parent.name.startswith("task_"):
            return task_dir, task_dir.parent.name, task_dir.name
        return task_dir, task_dir.name, "flat"

    versions = []
    for child in task_dir.iterdir():
        if not child.is_dir():
            continue
        version_num = _parse_version_dir(child)
        if version_num is None:
            continue
        if not (child / "task.yaml").exists():
            continue
        versions.append((version_num, child))

    if not versions:
        raise FileNotFoundError(
            f"No task.yaml or versioned vN/task.yaml found under: {task_dir}"
        )

    _, latest_dir = max(versions, key=lambda item: item[0])
    return latest_dir, task_dir.name, latest_dir.name


def _parse_suite(suite: str | None) -> set[str] | None:
    if suite and suite.lower() != "all":
        return {s.strip() for s in suite.split(",") if s.strip()}
    return None


def _load_task_list_paths(tasks_root: Path, task_list: Path) -> list[Path]:
    """Read ARCA-style task list JSONL and resolve candidate task roots.

    Each record should include "task_id" and "target". The recommended call is
    --dataset tasks --task-list batch_inputs/test_tasks.jsonl, which resolves to
    tasks/{target}/{task_id}. For convenience, --dataset tasks/openclaw also
    works and falls back to tasks_root/{task_id}.
    """
    if not task_list.exists():
        raise FileNotFoundError(f"Task list not found: {task_list}")

    paths: list[Path] = []
    seen: set[Path] = set()
    with open(task_list, encoding="utf-8") as f:
        for line_num, line in enumerate(f, 1):
            line = line.strip()
            if not line:
                continue
            try:
                item = json.loads(line)
            except json.JSONDecodeError as e:
                print(f"[WARN] Failed to parse {task_list}:{line_num}: {e}")
                continue

            task_id = item.get("task_id")
            target = item.get("target")
            if not task_id or not target:
                print(f"[WARN] Skipping {task_list}:{line_num}: missing task_id or target")
                continue

            candidates = [
                tasks_root / target / task_id,
                tasks_root / task_id,
            ]
            selected = next((p for p in candidates if p.exists()), candidates[0])
            if selected not in seen:
                paths.append(selected)
                seen.add(selected)

    return paths


def load_task(task_dir: Path) -> Task:
    """Load a single task from a flat or versioned task directory.

    Flat structure:
        task_xxx/
        ├── task.yaml
        ├── metadata.yaml
        ├── grader.py
        └── fixture/

    Versioned structure:
        task_xxx/
        ├── v1/
        └── v2/
            ├── task.yaml
            ├── metadata.yaml
            ├── grader.py
            └── fixture/
    """
    task_dir, task_id, version = resolve_task_dir(task_dir)
    task_yaml_path = task_dir / "task.yaml"
    metadata_yaml_path = task_dir / "metadata.yaml"

    with open(task_yaml_path, encoding="utf-8") as f:
        task_data = yaml.safe_load(f) or {}

    # Handle nested YAML format: some task.yaml files wrap name/prompt/category/tools
    # under a "task:" key while keeping judge_rubric/user_agent at the top level.
    if "task" in task_data and isinstance(task_data["task"], dict):
        task_inner = task_data["task"]
        # Merge nested fields into top level (top-level takes precedence)
        for key in ("name", "prompt", "category", "tools", "user_agent", "workspace"):
            if key not in task_data and key in task_inner:
                task_data[key] = task_inner[key]

    metadata = {}
    if metadata_yaml_path.exists():
        try:
            with open(metadata_yaml_path, encoding="utf-8") as f:
                metadata = yaml.safe_load(f) or {}
        except yaml.YAMLError:
            # metadata.yaml is optional; skip if malformed
            pass

    tools = _parse_tools(task_data.get("tools"))
    judge_rubric = _parse_judge_rubric(task_data.get("judge_rubric"))
    user_agent = _parse_user_agent(task_data.get("user_agent"))
    workspace_path = _parse_workspace_path(task_data.get("workspace"))

    fixture_dir = task_dir / "fixture"
    if not fixture_dir.exists():
        fixture_dir = None

    return Task(
        task_id=task_id,
        version=version,
        name=task_data.get("name", task_id),
        category=task_data.get("category", "unknown"),
        prompt=task_data.get("prompt", ""),
        task_dir=task_dir,
        tools=tools,
        judge_rubric=judge_rubric,
        metadata=metadata,
        fixture_dir=fixture_dir,
        workspace_path=workspace_path,
        user_agent=user_agent,
    )


def load_tasks(
    tasks_root: Path,
    suite: str | None = None,
    task_list: Path | None = None,
) -> list[Task]:
    """Load all tasks from the tasks root directory.

    Supports both flat and versioned layouts:
        tasks/openclaw/
        ├── task_pasb_xxx/
        │   ├── task.yaml              # flat
        └── task_safety_yyy/
            ├── v1/
            └── v2/                    # latest version is selected

    Args:
        tasks_root: Path to tasks directory (e.g., tasks/openclaw/)
        suite: Optional comma-separated list of task IDs to include.
               If None, load all tasks.
        task_list: Optional ARCA-style JSONL with task_id and target fields.

    Returns:
        List of Task objects, sorted by task_id.
    """
    if not tasks_root.exists():
        raise FileNotFoundError(f"Tasks directory not found: {tasks_root}")

    suite_ids = _parse_suite(suite)

    tasks = []
    if task_list is not None:
        candidate_dirs = _load_task_list_paths(tasks_root, task_list)
    else:
        candidate_dirs = [
            task_dir
            for task_dir in sorted(tasks_root.iterdir())
            if task_dir.is_dir() and task_dir.name.startswith("task_")
        ]

    for task_dir in candidate_dirs:
        if suite_ids and task_dir.name not in suite_ids:
            continue

        try:
            task = load_task(task_dir)
            tasks.append(task)
        except Exception as e:
            print(f"[WARN] Failed to load task {task_dir.name}: {e}")

    return tasks


def get_task_summary(tasks: list[Task]) -> dict[str, int]:
    """Get a summary of tasks by category."""
    summary: dict[str, int] = {}
    for task in tasks:
        summary[task.category] = summary.get(task.category, 0) + 1
    return summary
