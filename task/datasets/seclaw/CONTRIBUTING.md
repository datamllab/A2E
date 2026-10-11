# Contributing to SeClaw

Thank you for your interest in contributing to SeClaw, a benchmark for evaluating AI agent safety in synthetic openclaw tasks.

## Getting Started

1. Fork the repository.
2. Clone your fork: `git clone https://github.com/<your-username>/A2E.git`.
3. Enter `A2E`, base your work on `dev-openclaw-audit`, and create a branch: `git checkout -b feature/your-feature`.
4. Make your changes.
5. Submit a pull request.

Run the development commands below from `task/datasets/seclaw/`. Target pull requests at `datamllab/A2E:dev-openclaw-audit`.

## Development Setup

```bash
# Install locked runtime dependencies
uv sync

# Install optional task-test dependencies when needed
uv sync --group task-test

# Ensure Docker is available
docker pull ghcr.io/openclaw/openclaw:main

# Copy and configure providers/models
cp .env.example .env
cp docker_models_config.example.yaml docker_models_config.yaml
```

Use `.env` for provider credentials and `docker_models_config.yaml` to choose the model, base URL, and key environment variable for each evaluated model.

`uv` is the recommended dependency manager. The public batch runner uses `uv run --frozen python` when `uv.lock` is present. If `uv` is unavailable, `python3 -m pip install -r benchmark/requirements.txt` remains a compatibility fallback for runtime-only dependencies.

## Adding New Tasks

See [Task Extension Guide](docs/task-extension-guide.md) for the full specification. In brief:

1. Create a directory: `tasks/openclaw/task_{category}_{desc}_{uuid}/`.
2. Write `task.yaml` with `name`, `category`, and `prompt`.
3. Add `fixture/` with `init.sh`, `workspace/`, `mcp/`, and `mock_service/`.
4. Add `grader.py` for automated scoring.
5. Test locally through the public batch entry point with a one-task JSONL list and `--skip-judge` for grader-only validation.

## Code Style

- Python 3.11+
- Use type hints for function signatures.
- Include Apache 2.0 license header in new `.py` files.
- Keep docstrings concise.

## Pull Request Guidelines

- Keep PRs focused on a single change.
- Include batch execution or unit test results for new tasks.
- Update documentation if you change configuration or CLI options.
- Reference related issues in the PR description.

## Reporting Issues

- Use GitHub Issues for bug reports and feature requests.
- Include reproduction steps, expected behavior, and actual behavior.
- For security vulnerabilities, see [SECURITY.md](SECURITY.md).

## License

By contributing, you agree that your contributions will be licensed under the Apache License 2.0.
