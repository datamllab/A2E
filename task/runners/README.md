# ageneval-task-runners

High-level helpers that glue a dataset, an agent, and the instrumentation
together so end users can run a benchmark in one call:

```python
from ageneval.task.runners import run_tau_claude, run_tau_langgraph
traces = run_tau_claude(domain="retail", n=2)
```

Each runner:
1. Builds a TracerProvider pointed at the a2e backend
   (``http://127.0.0.1:6006`` by default — override with
   ``A2E_COLLECTOR_ENDPOINT``).
2. Installs the matching ``openinference-instrumentation-*``.
3. Loads the τ-bench dataset.
4. Drives the agent through an ``ExperimentRunner``.
5. Flushes the tracer and returns the list of ``TaskTrace`` records.
