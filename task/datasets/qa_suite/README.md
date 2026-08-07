# ageneval-task-qa-suite

A single config-driven adapter exposing **10 pure question-answering benchmarks**
(no sandbox, no tools, no skill/memory) loaded from HuggingFace.

Each benchmark is described by one `QABenchmark` row in `benchmarks.py` and is
registered as its own dataset name in `ageneval.task.runners.registry`.

| key | HF dataset | type | notes |
|---|---|---|---|
| `gpqa` | `Idavidrein/gpqa` | mc | **gated** — requires HF auth; loader raises on failure |
| `mmlu-pro` | `TIGER-Lab/MMLU-Pro` | mc | 10-way multiple choice |
| `arc-challenge` | `allenai/ai2_arc` | mc | ARC-Challenge split |
| `truthfulqa` | `truthful_qa` | mc | MC1 single-correct variant |
| `bbh` | `lukaemon/bbh` | freeform | BIG-Bench-Hard, boolean_expressions task |
| `agieval` | `hails/agieval-aqua-rat` | mc | AGIEval AQuA-RAT subset |
| `commonsenseqa` | `tau/commonsense_qa` | mc | 5-way multiple choice |
| `hellaswag` | `Rowan/hellaswag` | mc | sentence-completion as A/B/C/D |
| `openbookqa` | `allenai/openbookqa` | mc | 4-way multiple choice |
| `math` | `HuggingFaceH4/MATH-500` | numeric | MATH-500 competition problems |

## Usage

```python
from ageneval.task.datasets.qa_suite import load_qa_tasks, build_qa_binding, BENCHMARKS

tasks = load_qa_tasks("arc-challenge", n=10)
binding = build_qa_binding("arc-challenge")
```

## Adding a benchmark

Add one `QABenchmark` row to `BENCHMARKS` in `benchmarks.py` and one loop entry in
`registry.py`. No new file is required.
