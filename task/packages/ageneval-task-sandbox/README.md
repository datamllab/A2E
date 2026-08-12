# ageneval-task-sandbox

Synchronous **sandbox abstraction** for the A2E task layer. It lets a dataset
run an agent inside an isolated execution environment (a temp directory or a
docker container) so the agent can run shell commands and edit files, and so a
grader can apply a patch and run tests — the foundation for code-execution
datasets such as **SWE-bench**.

## Why synchronous?

A2E's `AgentBinding.tool_executor(name, args, state)` is synchronous, and
sandbox evaluation runs serially (one heavy container at a time). A sync API
(`subprocess.run` / `docker exec`) is therefore the simplest correct design and
requires **zero changes** to the existing agent runners — they call
`tool_executor` exactly as before, and the executor reaches the live sandbox
through `state["__sandbox__"]` (injected by `SandboxScoringRunner`) or the
`sandbox()` context accessor.

## Providers

| type     | class                       | mechanism                                  |
|----------|-----------------------------|--------------------------------------------|
| `local`  | `LocalSandboxEnvironment`   | `tempfile` workdir + `subprocess.run`      |
| `docker` | `DockerSandboxEnvironment`  | single container via `docker run/exec/cp/rm` (no compose) |

## Usage

```python
from ageneval.task.sandbox import SandboxSpec, sandbox_session

with sandbox_session(SandboxSpec("docker", {"image": "swebench/...", "cwd": "/testbed"})) as sb:
    sb.write_file("/tmp/x.txt", "hello")
    r = sb.exec(["bash", "-lc", "cat /tmp/x.txt"])
    assert r.stdout == "hello"
# container is removed on exit
```

## Provenance

The sandbox-abstraction design (base interface, provider registry, lifecycle,
context accessor) is **migrated from [inspect_ai](https://github.com/UKGovernmentBEIS/inspect_ai)**
(`src/inspect_ai/util/_sandbox/`), MIT-licensed, © UK AI Security Institute.
This is a clean re-implementation adapted to A2E's synchronous tool contract and
single-container docker model.
