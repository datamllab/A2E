# Jev as Judge

Jev (TypeSafe System One) is an extra score next to the existing LLM judge. It does not replace that judge. A full eval still writes the original annotation, and, for the four metrics below, a second annotation whose name ends in `_jev`.

Implementation: `eval/process_values/jev_dimension.py`. The client is `eval/core/jev_judge.py`. The key is read from `OPENROUTER_API_KEY` or `A2E_JEV_API_KEY`. It is not stored in the repo.

## Why only these four

Jev does not write a chain of thought. One request takes a state and one or more closed questions, and returns a choice or a yes-probability. Questions in the same request cannot see each other.

That is useful when a score can be turned into a small check against something already written in the trajectory:

1. The reference is recorded in the trace. It is not inferred by another model.
2. Each question covers one unit: one tool call, one tool name, one explicit sentence, or one repeated stretch that code has already cut out.
3. Code combines the answers. One failure makes the run fail. Jev is not asked to summarize the whole trajectory.

The other LLM metrics do not have that shape. `plan_grade`, `plan_goal_alignment`, `plan_completeness`, `plan_hallucination`, `hallucination`, and `conciseness` ask for an impression of a long trace. Splitting them into yes/no questions did not make Jev more accurate, because each small question was still an impression. Counting metrics stay on code.

On Terminal-Bench 2.1 experiments 21 and 22 (162 runs, 2570 tool calls), sending the whole trajectory to Jev did not fix those impression scores. Least-to-most prompting (Zhou et al., ICLR 2023), which asks easy questions first and feeds those answers into later questions, also did not. The gain showed up only after the reference and the unit were already isolated.

## The four scores

### `tool_invocation_jev`

The LLM metric asks whether every call in the trajectory has legal arguments. Jev does not see that list as one question.

- Schema comes from the trace: LLM-span `json_schema`, otherwise the TOOL-span parameter block. It is not inferred from the calls.
- Calls come from `tool_call_records` / `tool_calls_full`. One request contains one call and that tool's schema.
- The question is: does this call satisfy the schema? Required fields must be present and listed fields must have the right type. Extra fields are allowed, because the recorded bash schema only requires `command` as a string and does not set `additionalProperties: false`. Fields such as `timeout` are therefore legal under that schema.
- Code aggregates with AND. Any call that is not `correct`, or whose name has no schema, makes the run `incorrect`.
- No calls, names without arguments, or no recorded schema produce `unscored`.

On experiments 21 and 22 this matched a lenient schema check on 2527/2531 calls and 120/122 runs. A strict reading that treats extra fields as illegal is a different label. Under that reading the original LLM judge is closer, because Jev follows the schema text and does not add a "no extra fields" rule that the schema does not state.

### `tool_selection_jev`

The question is only whether the called name is on the menu recorded in the same schemas. It does not ask whether the tool was a good choice.

- Allowed names are the schema names from the trace.
- One call at a time. The question text contains both the name and the comma-separated menu: "Is NAME one of these allowed tools: ...?" A choice question that only says "Is call_tool one of allowed_tools?" marked legal names incorrect, so that form is not used.
- Yes if the returned probability is at least 0.5.
- Code aggregates with AND. Any name below 0.5 makes the run `incorrect`.
- No calls, or no menu, produces `unscored`.

On experiments 21 and 22 every recorded call name was already on the menu, and Jev agreed on 2570/2570 calls. The check is real, but this dataset does not contain an out-of-menu name, so it does not show that Jev catches a bad name.

`tool_selection` itself is not one of the 27 default matrix metrics. The LLM builder still exists. The Jev score is attached on a full-matrix run so this check is reported beside the other three.

### `plan_constraint_adherence_jev`

The LLM metric judges the whole plan against every constraint at once. The Jev score splits the task text first.

- Code copies explicit lines from the task instruction. A line is kept when it matches `do not`, `don't`, `must`, `should`, `only`, `exactly`, `required`, or `never`, or when it mentions a path such as `` `/ `` or `/app`. Lines that introduce the hidden test plan ("we will test", numbered test steps, "as a sanity check") are skipped.
- One request contains one of those sentences plus the tool steps (tool name and a clipped command or path).
- The question is: do these steps violate this explicit constraint? Labels are `adhered` and `violated`.
- Code aggregates with AND. Any `violated` answer makes the run `violated`.
- If no explicit sentence is found, the run is `unscored`.

This is the weakest of the four. The reference is a sentence, not a schema. On the same 162 runs, asking one sentence at a time was not more accurate than the original LLM judge. It is included because the unit is still one recorded sentence rather than a grade of the whole plan, and because the LLM score is kept for comparison.

### `repeated_tool_call_rate_jev`

The LLM metric already uses code to find repeated stretches and then asks a model whether they are a dead loop. The Jev score keeps that split and changes only the second step.

- Code finds candidate windows on tool calls only. A window is at least three consecutive calls with the same tool and the same or trivially varied arguments (digits in a long command are normalized), or an alternating two-call cycle of length at least four. At most three windows are kept. This step does not decide that a window is a loop.
- If there is no window, the label is `clean`, the score is 0, and Jev is not called.
- For each window, Jev sees up to six calls (head and tail if the window is longer), with clipped arguments and results. The question is: are these repeated calls leaving the environment unchanged? Yes means no new effect. No means a later call changed the result, recovered an error, or moved the task forward. Yes if the probability is at least 0.5.
- If any window is "unchanged", the label is `looping` and the score is the number of distinct tool names in the candidate windows. Otherwise the label is `clean` and the score is 0.
- No calls with arguments produces `unscored`.

On experiments 21 and 22, code found a window on 4 of 162 runs. Jev agreed with the previous LLM label on all four: progress that moved from 28% to 68% was not a loop; repeated `sed` of one disassembly and repeated `view` of one source range were loops. Agreement with the old LLM labels moved from 146/151 to 149/151. Two runs the old LLM called looping never reached Jev, because the locator did not group "read the next line range of the same file" as the same action.

## What is not changed

The original 27 metrics, their labels, and their LLM or code judges stay as they are. `server/`, `ui/`, and the rest of the repo are not part of this change. A full eval adds the four `_jev` names. It does not turn the other LLM metrics into Jev.
