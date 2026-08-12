# ageneval-task-core

Core abstractions for the A2E **task** layer.

Provides framework-agnostic primitives shared by every dataset adapter, agent
implementation, and experiment runner:

| Module | Purpose |
|---|---|
| `dataset.py`         | `TaskInput`, `Dataset` protocols |
| `agent.py`           | `AgentRunner` abstract base class |
| `result.py`          | `TaskTrace` dataclass returned by runners |
| `runner.py`          | `ExperimentRunner` that wires dataset + agent + tracer + a2e |
| `instrumentation.py` | `setup_instrumentation()` helper (OTLP → a2e) |

No agent / dataset / framework specifics live here — those go in sibling
workspace packages (`task/agents/*`, `task/datasets/*`, `task/runners`).
