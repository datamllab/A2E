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

"""OpenClaw CLI interaction for running agents inside Docker containers.

Handles gateway startup, agent creation, prompt execution, transcript
collection, and multi-turn dialogue through the OpenClaw CLI inside the container.
"""

import json
import logging
import re
import time
import uuid
from dataclasses import dataclass, field

from lib_docker import DockerContainer
from lib_tasks import UserAgentConfig
from lib_user_agent import UserAgentRunner

logger = logging.getLogger(__name__)

DEFAULT_THINKING = "medium"
DEFAULT_MAX_TURNS = 30
GATEWAY_STARTUP_TIMEOUT = 15  # reduced since --local mode doesn't strictly need gateway


@dataclass
class AgentResult:
    """Result of running an agent on a task."""

    task_id: str
    agent_id: str
    session_id: str
    transcript: list[dict] | None
    workspace_path: str | None
    exit_code: int
    stdout: str
    stderr: str
    elapsed_seconds: float
    error: str | None = None


def _slugify_model(model: str) -> str:
    """Convert a model name to a safe agent ID slug."""
    slug = re.sub(r"[^a-zA-Z0-9_-]", "-", model)
    slug = re.sub(r"-+", "-", slug).strip("-")
    return slug[:64] if slug else "agent"


def start_gateway(container: DockerContainer, timeout: int = GATEWAY_STARTUP_TIMEOUT) -> bool:
    """Start the OpenClaw gateway inside the container.

    The gateway is started as a background process (nohup).
    Note: When using `--local` mode, the gateway is not strictly required
    since the agent runs embedded. We start it anyway for compatibility
    but use a shorter health check timeout.

    Returns:
        True if gateway started successfully.
    """
    # Start gateway in background
    container.exec(
        "nohup openclaw gateway run --bind loopback > /tmp/openclaw-gateway.log 2>&1 &",
        user="node",
    )

    # Wait for gateway to be ready (with reduced timeout since --local mode
    # doesn't strictly need the gateway)
    logger.debug("Waiting for OpenClaw gateway to start...")
    start = time.time()
    while time.time() - start < timeout:
        # Try health endpoint first, then fall back to checking if HTTP server responds
        exit_code, stdout, _ = container.exec(
            "curl -sf http://127.0.0.1:18789/health 2>/dev/null || "
            "curl -sf http://127.0.0.1:18789/ 2>/dev/null | head -1 || echo NOT_READY"
        )
        if '"ok"' in stdout or '"status"' in stdout or '<!doctype' in stdout.lower():
            logger.debug("Gateway is ready (%.1fs)", time.time() - start)
            return True
        time.sleep(2)

    # Check if gateway process is running
    exit_code, stdout, _ = container.exec("pgrep -f 'openclaw gateway' || echo NO_PROCESS")
    if "NO_PROCESS" in stdout:
        logger.error("Gateway process not found")
        _, log_stdout, _ = container.exec("cat /tmp/openclaw-gateway.log 2>/dev/null | tail -20")
        logger.error("Gateway log: %s", log_stdout[:500])
        return False

    logger.warning("Gateway health check timed out, but process is running. Proceeding.")
    return True


def _save_mcp_config(container: DockerContainer) -> dict | None:
    """Save MCP server configuration from openclaw.json before onboard overwrites it.

    Returns:
        The mcp.servers dict from openclaw.json, or None if no MCP servers configured.
    """
    exit_code, stdout, _ = container.exec("cat /home/node/.openclaw/openclaw.json 2>/dev/null")
    if exit_code != 0 or not stdout.strip():
        logger.warning("Could not read openclaw.json before onboard")
        return None

    try:
        config = json.loads(stdout)
        logger.debug("openclaw.json before onboard: %s", json.dumps(config, indent=2)[:500])
        # OpenClaw stores MCP servers under "mcp.servers"
        mcp_config = config.get("mcp", {})
        mcp_servers = mcp_config.get("servers", {})
        # Also check legacy "mcpServers" key
        if not mcp_servers:
            mcp_servers = config.get("mcpServers", {})
        if mcp_servers:
            logger.debug("Saved MCP config with %d server(s): %s",
                        len(mcp_servers), ", ".join(mcp_servers.keys()))
            return mcp_servers
        else:
            logger.info("No MCP servers found in openclaw.json before onboard")
    except json.JSONDecodeError as e:
        logger.warning("Failed to parse openclaw.json: %s", e)

    return None


def _restore_mcp_config(container: DockerContainer, mcp_servers: dict) -> None:
    """Re-register MCP servers that were wiped by openclaw onboard.

    Uses `openclaw mcp set <name> '<json>'` to restore each server.
    Skips servers that already exist in openclaw.json after onboard.
    """
    # Check which MCP servers still exist after onboard
    existing_servers = set()
    exit_code, stdout, _ = container.exec("cat /home/node/.openclaw/openclaw.json 2>/dev/null")
    if exit_code == 0 and stdout.strip():
        try:
            config = json.loads(stdout)
            existing = config.get("mcp", {}).get("servers", {})
            if not existing:
                existing = config.get("mcpServers", {})
            existing_servers = set(existing.keys())
        except json.JSONDecodeError:
            pass

    for name, config in mcp_servers.items():
        if name in existing_servers:
            logger.debug("MCP server '%s' already exists after onboard, skipping restore", name)
            continue

        config_json = json.dumps(config, ensure_ascii=False)
        # Escape single quotes for shell
        config_json_escaped = config_json.replace("'", "'\\''")
        cmd = f"openclaw mcp set {name} '{config_json_escaped}'"
        logger.debug("Restoring MCP server: %s -> %s", name, config_json[:200])
        exit_code, stdout, stderr = container.exec(cmd, timeout=30)
        if exit_code != 0:
            logger.warning("Failed to restore MCP server '%s': %s", name, stderr[:200])
        else:
            logger.debug("Restored MCP server: %s (stdout: %s)", name, stdout[:100])


def _diagnose_mcp(container: DockerContainer) -> None:
    """Log diagnostic information about MCP registration status."""
    # Check openclaw.json content (fast, reliable)
    exit_code, stdout, _ = container.exec("cat /home/node/.openclaw/openclaw.json 2>/dev/null")
    if exit_code == 0 and stdout.strip():
        try:
            config = json.loads(stdout)
            mcp_servers = config.get("mcp", {}).get("servers", {})
            if not mcp_servers:
                mcp_servers = config.get("mcpServers", {})
            if mcp_servers:
                logger.debug("MCP servers in openclaw.json: %s", ", ".join(mcp_servers.keys()))
                for name, srv in mcp_servers.items():
                    logger.debug("  %s: %s", name, json.dumps(srv)[:200])
            else:
                logger.warning("No MCP servers found in openclaw.json")
        except json.JSONDecodeError:
            logger.warning("openclaw.json is not valid JSON: %s", stdout[:200])
    else:
        logger.warning("Could not read openclaw.json for diagnosis")

    # Check openclaw mcp list (may be slow, non-fatal)
    try:
        exit_code, stdout, stderr = container.exec("openclaw mcp list 2>&1", timeout=30)
        logger.debug("openclaw mcp list: exit=%d stdout=%s", exit_code, stdout[:500])
    except Exception as e:
        logger.warning("openclaw mcp list timed out or failed: %s", e)


def _cleanup_sessions(container: DockerContainer, agent_id: str) -> None:
    """Clean up existing sessions for an agent to avoid session recovery issues.

    OpenClaw may send 'Continue where you left off' if stale sessions exist.
    """
    # Remove session files for this agent
    container.exec(
        f"rm -rf /home/node/.openclaw/agents/{agent_id}/sessions/ 2>/dev/null || true"
    )
    # Run session cleanup
    container.exec(f"openclaw sessions cleanup --agent {agent_id} 2>/dev/null || true")


def create_agent(
    container: DockerContainer,
    model: str,
    agent_id: str | None = None,
    workspace: str = "/home/node/workspace",
    api_key: str | None = None,
    base_url: str | None = None,
) -> str:
    """Create an OpenClaw agent inside the container.

    Uses `openclaw onboard` to configure the model provider, then creates
    an agent with the specified model. Preserves MCP server configuration
    that may have been set by init.sh, since onboard overwrites openclaw.json.

    Args:
        container: Running DockerContainer.
        model: Model identifier (e.g., "your-model-id").
        agent_id: Optional agent ID. Generated from model if not provided.
        workspace: Workspace path inside the container.
        api_key: API key for the model provider.
        base_url: Base URL for the model provider.

    Returns:
        The agent_id used.
    """
    if agent_id is None:
        agent_id = f"bench-{_slugify_model(model)}"

    # Save MCP config before onboard (which overwrites openclaw.json)
    mcp_servers = _save_mcp_config(container)

    # Diagnose MCP state before onboard
    _diagnose_mcp(container)

    # Run onboard to configure the model provider if api_key is provided
    if api_key and base_url:
        logger.debug("Onboarding model provider for %s...", model)
        onboard_cmd = (
            f"openclaw onboard "
            f"--auth-choice custom-api-key "
            f"--custom-api-key '{api_key}' "
            f"--custom-base-url '{base_url}' "
            f"--custom-model-id '{model}' "
            f"--custom-compatibility openai "
            f"--accept-risk "
            f"--non-interactive 2>&1"
        )
        exit_code, stdout, stderr = container.exec(onboard_cmd, timeout=300)
        if exit_code != 0:
            logger.warning("Onboard completed with warnings: %s", stderr[:200])
        else:
            logger.debug("Onboard completed successfully")

    # Diagnose MCP state after onboard
    logger.debug("MCP state after onboard:")
    _diagnose_mcp(container)

    # Restore MCP servers that onboard wiped
    if mcp_servers:
        _restore_mcp_config(container, mcp_servers)
    else:
        logger.warning("No MCP servers to restore after onboard")

    # Diagnose MCP state after restore
    logger.debug("MCP state after restore:")
    _diagnose_mcp(container)

    # Clean up any existing agent with the same ID
    container.exec(f"openclaw agents delete {agent_id} 2>/dev/null || true")

    # Determine the full model ID with provider prefix
    # After onboard, the provider is named based on the base_url domain.
    # OpenClaw needs the full provider/model format (e.g., custom-api-example-com/your-model)
    full_model = model
    if "/" not in model and base_url:
        # Derive provider name from base_url (same logic as openclaw onboard)
        from urllib.parse import urlparse
        parsed = urlparse(base_url)
        host = parsed.hostname or ""
        provider_slug = "custom-" + host.replace(".", "-")
        full_model = f"{provider_slug}/{model}"
        logger.debug("Using full model ID: %s (derived from base_url)", full_model)

    # Create the agent
    exit_code, stdout, stderr = container.exec(
        f"openclaw agents add {agent_id} --model {full_model} "
        f"--workspace {workspace} --non-interactive"
    )

    if exit_code != 0:
        raise RuntimeError(
            f"Failed to create agent {agent_id}: exit={exit_code}\n"
            f"stdout: {stdout[:500]}\nstderr: {stderr[:500]}"
        )

    # Clean up stale sessions to prevent "Continue where you left off"
    _cleanup_sessions(container, agent_id)

    logger.debug("Agent created: %s (model: %s)", agent_id, model)
    return agent_id


def run_prompt(
    container: DockerContainer,
    agent_id: str,
    prompt: str,
    session_id: str | None = None,
    thinking: str = DEFAULT_THINKING,
    max_turns: int = DEFAULT_MAX_TURNS,
    timeout_seconds: int = 600,
) -> AgentResult:
    """Execute a prompt against an OpenClaw agent inside the container.

    Args:
        container: Running DockerContainer.
        agent_id: The agent to use.
        prompt: The task prompt to send.
        session_id: Optional session ID for the conversation.
        thinking: OpenClaw thinking level (off/minimal/low/medium/high/xhigh).
        max_turns: Maximum number of agent turns (not supported by all OpenClaw versions).
        timeout_seconds: Maximum execution time.

    Returns:
        AgentResult with transcript and execution details.
    """
    if session_id is None:
        session_id = f"bench-{uuid.uuid4().hex[:12]}"

    # Build the openclaw agent command
    # Escape the prompt for shell
    escaped_prompt = prompt.replace("'", "'\\''")
    cmd = (
        f"openclaw agent "
        f"--local "
        f"--agent {agent_id} "
        f"--session-id {session_id} "
        f"--thinking {thinking} "
        f"--json "
        f"--message '{escaped_prompt}'"
    )

    logger.debug("Running prompt for agent %s (session: %s)...", agent_id, session_id)
    start_time = time.time()

    exit_code, stdout, stderr = container.exec(cmd, timeout=timeout_seconds)
    elapsed = time.time() - start_time

    logger.info("Agent execution completed in %.1fs (exit_code=%d)", elapsed, exit_code)

    if exit_code != 0:
        logger.warning("Agent execution failed (exit_code=%d): %s", exit_code, stderr[:300])

    # Collect the transcript
    transcript = container.get_transcript(agent_id)

    # If no transcript from files, try parsing JSON from stdout
    if transcript is None and stdout.strip():
        stdout_text = stdout.strip()
        try:
            result = json.loads(stdout_text)
            # Some openclaw versions output JSON results
            if isinstance(result, dict):
                messages = result.get("messages", result.get("transcript", []))
                if messages:
                    transcript = messages
                elif isinstance(result.get("payloads"), list):
                    texts = [
                        str(payload.get("text"))
                        for payload in result["payloads"]
                        if isinstance(payload, dict) and payload.get("text")
                    ]
                    if texts:
                        transcript = [{
                            "type": "message",
                            "message": {
                                "role": "assistant",
                                "content": [{"type": "text", "text": "\n".join(texts)}],
                            },
                        }]
                else:
                    text = (
                        result.get("text")
                        or result.get("response")
                        or result.get("output")
                        or result.get("content")
                    )
                    message = result.get("message")
                    if text is None and isinstance(message, dict):
                        text = message.get("content") or message.get("text")
                    elif text is None and isinstance(message, str):
                        text = message
                    if text is not None:
                        transcript = [{
                            "type": "message",
                            "message": {
                                "role": "assistant",
                                "content": [{"type": "text", "text": str(text)}],
                            },
                        }]
        except json.JSONDecodeError:
            transcript = [{
                "type": "message",
                "message": {
                    "role": "assistant",
                    "content": [{"type": "text", "text": stdout_text}],
                },
            }]

    return AgentResult(
        task_id=container.task_id,
        agent_id=agent_id,
        session_id=session_id,
        transcript=transcript,
        workspace_path="/home/node/workspace",
        exit_code=exit_code,
        stdout=stdout,
        stderr=stderr,
        elapsed_seconds=elapsed,
        error=stderr[:500] if exit_code != 0 else None,
    )


def setup_agent_in_container(
    container: DockerContainer,
    model: str,
    api_key: str | None = None,
    base_url: str | None = None,
) -> str:
    """Start gateway and create an agent, returning the agent_id.

    This is the common setup shared by single-turn and multi-turn execution.
    The caller is responsible for running prompts via run_prompt().

    Args:
        container: Running DockerContainer (already started with fixture deployed).
        model: Model identifier.
        api_key: API key for the model provider.
        base_url: Base URL for the model provider.

    Returns:
        The agent_id for subsequent run_prompt() calls.
    """
    start_gateway(container)
    return create_agent(container, model, api_key=api_key, base_url=base_url)


def run_task_in_container(
    container: DockerContainer,
    model: str,
    prompt: str,
    thinking: str = DEFAULT_THINKING,
    max_turns: int = DEFAULT_MAX_TURNS,
    timeout_seconds: int = 600,
    api_key: str | None = None,
    base_url: str | None = None,
) -> AgentResult:
    """Full pipeline: start gateway, create agent, run prompt, collect results.

    Args:
        container: Running DockerContainer (already started with fixture deployed).
        model: Model identifier.
        prompt: Task prompt.
        thinking: OpenClaw thinking level.
        max_turns: Maximum agent turns.
        timeout_seconds: Execution timeout.
        api_key: API key for the model provider.
        base_url: Base URL for the model provider.

    Returns:
        AgentResult with transcript and execution details.
    """
    agent_id = setup_agent_in_container(container, model, api_key=api_key, base_url=base_url)
    return run_prompt(
        container, agent_id, prompt,
        thinking=thinking,
        max_turns=max_turns,
        timeout_seconds=timeout_seconds,
    )


# ---------------------------------------------------------------------------
# Multi-turn support
# ---------------------------------------------------------------------------


@dataclass
class RoundResult:
    """Result of a single round in a multi-turn conversation."""

    round: int
    agent_result: AgentResult
    agent_response_preview: str
    user_message: str = ""


@dataclass
class MultiTurnResult:
    """Result of a complete multi-turn conversation."""

    task_id: str
    agent_id: str
    mode: str  # "scripted", "querylist", "adaptive", or "user_agent_server"
    max_rounds: int
    total_rounds: int
    stop_reason: str
    rounds: list[RoundResult] = field(default_factory=list)
    merged_transcript: list[dict] | None = None
    elapsed_seconds: float = 0.0
    error: str | None = None


def _extract_tool_calls_from_transcript(transcript: list[dict]) -> list[dict]:
    """Extract tool call names from a transcript for stop condition checking."""
    tool_calls = []
    if not transcript:
        return tool_calls
    for entry in transcript:
        rec_type = entry.get("type", "")
        if rec_type == "message":
            msg = entry.get("message", {})
            content = msg.get("content", [])
            if isinstance(content, list):
                for item in content:
                    if item.get("type") == "toolCall":
                        tool_calls.append({"name": item.get("name", "")})
        elif rec_type == "toolCall":
            tool_calls.append({"name": entry.get("name", "")})
    return tool_calls


def _merge_transcripts(
    round_transcripts: list[list[dict]],
    round_count: int,
) -> list[dict]:
    """Merge per-round transcripts into a single transcript with round markers.

    Injects {"type": "round_boundary", "round": N} markers between rounds
    and adds "_round" field to each message entry.
    """
    merged = []
    for i, transcript in enumerate(round_transcripts, start=1):
        merged.append({
            "type": "round_boundary",
            "round": i,
            "timestamp": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
        })
        for entry in transcript:
            entry_copy = dict(entry)
            entry_copy["_round"] = i
            merged.append(entry_copy)
    return merged


def run_conversation(
    container: DockerContainer,
    model: str,
    prompt: str,
    user_agent_config: UserAgentConfig,
    thinking: str = DEFAULT_THINKING,
    max_turns: int = DEFAULT_MAX_TURNS,
    timeout_seconds: int = 600,
    api_key: str | None = None,
    base_url: str | None = None,
) -> MultiTurnResult:
    """Run a multi-turn conversation with a simulated user agent.

    Each round sends a message via `openclaw agent --local` as an independent
    call. Context continuity relies on shared workspace state (files, tool
    results). Optionally, conversation history can be injected into follow-up
    messages via inject_context.

    Args:
        container: Running DockerContainer (already started with fixture deployed).
        model: Model identifier.
        prompt: Initial task prompt (round 1).
        user_agent_config: Configuration for the simulated user.
        thinking: OpenClaw thinking level.
        max_turns: Maximum agent turns per round.
        timeout_seconds: Execution timeout per round.
        api_key: API key for the model provider.
        base_url: Base URL for the model provider.

    Returns:
        MultiTurnResult with per-round details and merged transcript.
    """
    start_time = time.time()
    user_agent = UserAgentRunner(user_agent_config, initial_prompt=prompt)

    # Setup agent (gateway + create)
    agent_id = setup_agent_in_container(container, model, api_key=api_key, base_url=base_url)

    round_results: list[RoundResult] = []
    round_transcripts: list[list[dict]] = []
    stop_reason = ""
    total_rounds = 0

    for round_num in range(1, user_agent.max_rounds + 1):
        # Get the message for this round
        message = user_agent.get_message_for_round(round_num)
        agent_last_response = ""

        # For adaptive mode after round 1, generate message via LLM
        if round_num > 1 and user_agent.mode == "adaptive":
            if round_results:
                agent_last_response = round_results[-1].agent_response_preview
            adaptive_resp = user_agent.generate_adaptive_message(
                round_num, agent_last_response,
            )
            if adaptive_resp is None or not adaptive_resp.should_continue:
                logger.info(
                    "[%s] Adaptive agent decided to stop at round %d",
                    container.task_id, round_num,
                )
                stop_reason = "adaptive_agent_stopped"
                break
            message = adaptive_resp.next_query

        # For user_agent_server mode after round 1, generate message via LLM or HTTP
        if round_num > 1 and user_agent.mode == "user_agent_server":
            if round_results:
                agent_last_response = round_results[-1].agent_response_preview

            if user_agent.config.server_url:
                # HTTP mode: call external server
                server_resp = user_agent.generate_http_server_message(
                    round_num, agent_last_response,
                )
            else:
                # In-process mode: call LLM directly with server-style prompt
                server_resp = user_agent.generate_server_message(
                    round_num, agent_last_response,
                )

            if server_resp is None or not server_resp.should_continue:
                logger.info(
                    "[%s] User agent server decided to stop at round %d",
                    container.task_id, round_num,
                )
                stop_reason = "user_agent_server_stopped"
                break
            message = server_resp.next_query

        if message is None:
            # No more messages in scripted mode
            logger.info(
                "[%s] No message for round %d, ending conversation",
                container.task_id, round_num,
            )
            break

        # Apply context injection if configured
        formatted_message = user_agent.format_message_for_round(
            round_num, message, agent_last_response=agent_last_response,
        )

        logger.info(
            "[%s] Round %d/%d: sending message (%d chars)",
            container.task_id, round_num, user_agent.max_rounds,
            len(formatted_message),
        )

        # Run this round
        result = run_prompt(
            container, agent_id, formatted_message,
            thinking=thinking,
            max_turns=max_turns,
            timeout_seconds=timeout_seconds,
        )

        # Get agent's text response for this round
        response_text = container.get_last_assistant_text(agent_id)
        response_preview = response_text[:500] if response_text else ""

        # Collect transcript for this round
        round_transcript = result.transcript or []
        round_transcripts.append(round_transcript)

        # Record round info in user_agent for context injection
        user_agent.record_round(
            round_num=round_num,
            user_message=message,
            agent_response_preview=response_preview,
            elapsed_seconds=result.elapsed_seconds,
        )

        round_results.append(RoundResult(
            round=round_num,
            agent_result=result,
            agent_response_preview=response_preview,
            user_message=message,
        ))
        total_rounds = round_num

        # Check stop conditions
        tool_calls = _extract_tool_calls_from_transcript(round_transcript)
        should_stop, reason = user_agent.check_stop_conditions(
            round_num, response_text, tool_calls=tool_calls,
        )
        if should_stop:
            stop_reason = reason
            break

        # If the agent errored out, stop
        if result.exit_code != 0:
            stop_reason = f"agent_error:exit_code_{result.exit_code}"
            break

    # Merge all round transcripts
    merged = _merge_transcripts(round_transcripts, total_rounds)

    elapsed = time.time() - start_time
    if not stop_reason:
        stop_reason = "max_rounds_reached"

    return MultiTurnResult(
        task_id=container.task_id,
        agent_id=agent_id,
        mode=user_agent.mode,
        max_rounds=user_agent.max_rounds,
        total_rounds=total_rounds,
        stop_reason=stop_reason,
        rounds=round_results,
        merged_transcript=merged,
        elapsed_seconds=elapsed,
    )
