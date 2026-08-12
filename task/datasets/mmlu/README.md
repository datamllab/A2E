# ageneval-task-mmlu

MMLU (Massive Multitask Language Understanding) adapter — 57-subject multi-choice exam.

- HF dataset: `cais/mmlu`
- Type: QA (no tools), 4-way multiple choice (A/B/C/D)

Usage:

```python
from ageneval.task.datasets.mmlu import load_mmlu_tasks, build_mmlu_binding
tasks = load_mmlu_tasks(subset="all", n=10)
binding = build_mmlu_binding()
```
