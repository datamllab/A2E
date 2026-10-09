# Evaluation

A<sup>2</sup>E provides a unified evaluation pipeline for analyzing agent executions from
both process and outcome perspectives. After an experiment is completed,
collected trajectories can be evaluated across multiple dimensions of agent
behavior, including planning, tool usage, memory, correctness, efficiency, and
safety.

The evaluation workflow consists of two steps:

1. Start the A<sup>2</sup>E server to access stored experiment trajectories.
2. Run the evaluation pipeline on a selected experiment.

A<sup>2</sup>E supports:

- **Full evaluation**: run all available metrics for a comprehensive analysis.
- **Targeted evaluation**: evaluate specific aspects of agent behavior.

## Start A<sup>2</sup>E Server

Before running evaluations, start the server (same default endpoint as the root README):

```bash
# from repo root
bash scripts/start.sh                 # → http://localhost:6006
```

Or start the API only:

```bash
cd server
uv run a2e serve                     # → http://localhost:6006
```

The server exposes experiment data through:

```text
HTTP endpoint: http://localhost:6006
```

## Run All Evaluations

To evaluate an experiment across all supported metrics:

```bash
cd server

uv run python ../eval/scripts/run_eval.py \
  --base-url http://localhost:6006 \
  --experiment-id <experiment_id> \
  --part all
```

The `<experiment_id>` should correspond to an existing experiment stored in the
A<sup>2</sup>E database.

`--part all` also writes four extra Jev scores (`*_jev`) next to the original
LLM annotations. Export `OPENROUTER_API_KEY` or `A2E_JEV_API_KEY` first. See
[Jev as judge](#jev-as-judge).

## Run Specific Evaluations

A<sup>2</sup>E supports evaluation across multiple dimensions of agent behavior:

| Metric | Description |
|--------|-------------|
| `plan` | Evaluates planning quality and decision-making behavior |
| `memory` | Legacy alias for faithfulness checks under `safety` |
| `tool` | Evaluates tool selection and tool execution behavior |
| `correct` | Measures final task completion correctness |
| `efficiency` | Analyzes execution efficiency, resource usage, and answer conciseness |
| `safety` | Evaluates safety-related behaviors |

For example, to evaluate only the planning capability:

```bash
cd server

uv run python ../eval/scripts/run_eval.py \
  --base-url http://localhost:6006 \
  --experiment-id <experiment_id> \
  --part plan
```

## Supported Evaluation Parts

The available evaluation modules are:

```text
plan
memory    # legacy alias → safety (faithfulness)
tool
correct
efficiency
safety
```

Each evaluation module operates on recorded agent trajectories and produces
metrics for analyzing agent behavior and comparing different agent systems.

## Metric matrix (26 metrics)

The current evaluation matrix defines **26 deduped metrics** (15 LLM + 11 CODE)
across plan, tool, correct, efficiency, and safety. For plain-language definitions,
implementation notes, benchmark lineage, and diagnostic guidance, see:

- **English:** [METRICS_MATRIX_README.md](METRICS_MATRIX_README.md)
- **中文:** [METRICS_MATRIX_README_zh.md](METRICS_MATRIX_README_zh.md)

Catalog: `metrics_catalog.json` · Groups: `core/metric_groups.py`

## Jev as judge

Jev (TypeSafe System One) is an extra score next to the existing LLM judge. It does not replace that judge. A full eval still writes the original annotation, and, for the four metrics below, a second annotation whose name ends in `_jev`.

Implementation: `eval/process_values/jev_dimension.py`. The client is `eval/core/jev_judge.py`. The key is read from `OPENROUTER_API_KEY` or `A2E_JEV_API_KEY`. It is not stored in the repo.

Terminal-Bench 2.1 experiment means for `gpt-5.6-sol` are in `metrics_catalog.json` under `jev_dimension.tb21_results`.

### How to use

Jev is not a separate runner. Start the A<sup>2</sup>E server, export a key that can call OpenRouter System One (`jev-latest`), then use the same `run_eval.py` command as above.

```bash
export OPENROUTER_API_KEY=...   # or A2E_JEV_API_KEY
```

`--part all` attaches the four `*_jev` names automatically. `--part plan` and `--part tool` attach the matching twins (`plan_constraint_adherence_jev`, `tool_invocation_jev`, `repeated_tool_call_rate_jev`). To score only Jev:

```bash
cd server

uv run python ../eval/scripts/run_eval.py \
  --base-url http://localhost:6006 \
  --experiment-id <experiment_id> \
  --metrics tool_invocation_jev,tool_selection_jev,plan_constraint_adherence_jev,repeated_tool_call_rate_jev
```

Each finished run stores a second annotation under `<metric>_jev`. The original LLM annotation is unchanged. Without a key, the `*_jev` metrics fail. `A2E_JEV_URL` overrides the default `https://openrouter.ai/api/v1/systemone`.

### Why only these four

Jev does not write a chain of thought. One request takes a state and one or more closed questions, and returns a choice or a yes-probability. Questions in the same request cannot see each other.

That is useful when a score can be turned into a small check against something already written in the trajectory:

1. The reference is recorded in the trace. It is not inferred by another model.
2. Each question covers one unit: one tool call, one tool name, one explicit sentence, or one repeated stretch that code has already cut out.
3. Jev's probability on that unit is the score. The task score is the mean of those probabilities. The experiment number is the mean of the task scores, excluding items Jev could not score.

The other LLM metrics do not have that shape. `plan_grade`, `plan_goal_alignment`, `plan_completeness`, `plan_hallucination`, `hallucination`, and `conciseness` ask for an impression of a long trace. Splitting them into yes/no questions did not make Jev more accurate, because each small question was still an impression. Counting metrics stay on code.

On Terminal-Bench 2.1 experiments 21 and 22 (162 runs, 2570 tool calls), sending the whole trajectory to Jev did not fix those impression scores. Least-to-most prompting (Zhou et al., ICLR 2023), which asks easy questions first and feeds those answers into later questions, also did not. The gain showed up only after the reference and the unit were already isolated.

### The four scores

#### `tool_invocation_jev`

[0, 1], higher is better.

- Schema comes from the trace: LLM-span `json_schema`, otherwise the TOOL-span parameter block. It is not inferred from the calls.
- Calls come from `tool_call_records` / `tool_calls_full`. One request contains one call and that tool's schema.
- The question is: does this call satisfy the schema? Required fields must be present and listed fields must have the right type. Extra fields are allowed, because the recorded bash schema only requires `command` as a string and does not set `additionalProperties: false`. Fields such as `timeout` are therefore legal under that schema.
- The task score is the mean of P(correct) across calls. The label is `incorrect` if any call is not `correct` or has no schema.
- No calls, names without arguments, or no recorded schema produce `unscored`.

#### `tool_selection_jev`

[0, 1], higher is better.

- Allowed names are the schema names from the trace.
- One call at a time. The question text contains both the name and the comma-separated menu: "Is NAME one of these allowed tools: ...?" A choice question that only says "Is call_tool one of allowed_tools?" marked legal names incorrect, so that form is not used.
- The task score is the mean of the yes-probabilities. The label is `incorrect` if any name is below 0.5.
- No calls, or no menu, produces `unscored`.
- This check does not ask whether the tool was a good choice.

`tool_selection` itself is not one of the 27 default matrix metrics. The LLM builder still exists. The Jev score is attached on a full-matrix run so this check is reported beside the other three.

#### `plan_constraint_adherence_jev`

[0, 1], higher is better.

- Code copies explicit lines from the task instruction. A line is kept when it matches `do not`, `don't`, `must`, `should`, `only`, `exactly`, `required`, or `never`, or when it mentions a path such as `` `/ `` or `/app`. Lines that introduce the hidden test plan ("we will test", numbered test steps, "as a sanity check") are skipped.
- One request contains one of those sentences plus the tool steps (tool name and a clipped command or path).
- The question is: do these steps violate this explicit constraint? Labels are `adhered` and `violated`.
- The task score is the mean of P(adhered). The label is `violated` if any sentence is `violated`.
- If no explicit sentence is found, the run is `unscored`.

#### `repeated_tool_call_rate_jev`

[0, 1], higher is better.

- Code finds candidate windows on tool calls only. A window is at least three consecutive calls with the same tool and the same or trivially varied arguments (digits in a long command are normalized), or an alternating two-call cycle of length at least four. At most three windows are kept. This step does not decide that a window is a loop.
- If there is no window, the label is `clean`, the score is 1, and Jev is not called.
- For each window, Jev sees up to six calls (head and tail if the window is longer), with clipped arguments and results. The question is: are these repeated calls leaving the environment unchanged? Yes means no new effect. No means a later call changed the result, recovered an error, or moved the task forward.
- Each window scores `1 - P(unchanged)`. The task score is the mean of those values. The label is `looping` if any window has P(unchanged) ≥ 0.5.
- No calls with arguments produces `unscored`.

### What is not changed

The original 27 metrics, their labels, and their LLM or code judges stay as they are. `server/`, `ui/`, and the rest of the repo are not part of this change. A full eval adds the four `_jev` names. It does not turn the other LLM metrics into Jev.
