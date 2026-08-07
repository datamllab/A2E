# ageneval-task-swe-bench

SWE-bench adapter for A2E — the first **sandboxed** (`kind="sandbox"`) dataset.
An agent fixes a real GitHub issue inside a docker container; the official
`swebench` grader decides whether the fix `resolved` the issue.

## Variants

| registry key          | source                              | sandbox | grading            |
|-----------------------|-------------------------------------|---------|--------------------|
| `swe-bench-lite`      | `princeton-nlp/SWE-bench_Lite` (300)| docker  | official `swebench`|
| `swe-bench-verified`  | `princeton-nlp/SWE-bench_Verified` (500) | docker | official `swebench`|

## How it works

```
SandboxScoringRunner(inner=<any agent>, score_fn=score_swe_bench, setup_fn=setup_swe_bench)
  → docker run swebench/sweb.eval.x86_64.<id>   (repo at base_commit in /testbed)
  → agent uses bash + str_replace_editor (executed via the sandbox) to edit code
  → git diff captured as model_patch
  → official eval_script run in-container; log parsed by swebench → resolved
```

The agent is **unchanged**: it calls `binding.tool_executor` as always; the live
sandbox is injected into `state["__sandbox__"]`.

## Dependencies

* Loading is `swebench`-free (image name computed locally) so the registry stays
  light. Only **grading** needs `swebench`.
* Grading uses the official `swebench` package via an **isolated** `uv run --with
  swebench` subprocess (see `_grade_helper.py`), so `swebench` never enters the
  main A2E lock. To install it into the main env instead:
  `uv sync --package ageneval-task-swe-bench --extra grade --index-strategy unsafe-best-match`.

## Prerequisites for real variants

* docker available on the server (the worker preflights this);
* network access to pull `swebench/sweb.eval.*` images from Docker Hub;
* an LLM endpoint (`A2E_MODEL` + OpenAI/Anthropic-compatible keys).

## Provenance

SWE-bench: Jimenez et al., *SWE-bench: Can Language Models Resolve Real-World
GitHub Issues?* Grading via the official
[`swebench`](https://github.com/princeton-nlp/SWE-bench) package. Sandbox
abstraction migrated from inspect_ai (see `ageneval-task-sandbox`).
