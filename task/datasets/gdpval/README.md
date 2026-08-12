# ageneval-task-gdpval

GDPval dataset adapter for A2E.

**Source:** [`openai/gdpval`](https://huggingface.co/datasets/openai/gdpval) (OpenAI) —
1,320 real-world, economically valuable knowledge-work tasks across 44 occupations
in 9 GDP sectors. The public HF split exposes the open *gold* subset.

## Shape

Tool-less **deliverable-generation** task (no sandbox, like `humaneval` / `qa_suite`):

- `prompt` → agent instruction (attachment file names are surfaced as a note; the
  binary reference files themselves are NOT downloaded — a text-only endpoint can't
  ingest xlsx/pdf/pptx).
- `rubric_pretty` → carried in `expected_outputs[0]` as the grading reference.
- The agent's full reply is captured as the deliverable (`final_answer`).

## Recommended evaluator

`llm_judge` — an LLM-as-judge scores the produced deliverable against the rubric.
There is no exact-match ground truth.

## Run

```bash
cd task
uv run python examples/run_experiment.py \
    --dataset gdpval-aa --agent agno --model qwen-max \
    --evaluators llm_judge --n 3
```

Change the model via `--model` / `A2E_MODEL`; the API endpoint via
`OPENAI_API_BASE` + `OPENAI_API_KEY` (see repo `.env`).
