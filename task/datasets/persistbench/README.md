# ageneval-task-persistbench

PersistBench — long-horizon **knowledge persistence** benchmark (model must
remember facts/preferences across many turns).

- HF dataset: configurable via ``hf_id`` argument (no canonical name yet); falls
  back to a tiny vendored sample so smoke tests work offline.
- Type: QA over conversational context (no tools).
