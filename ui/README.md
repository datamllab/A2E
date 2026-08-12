# ui — A2E Experiment Viewer (React + Vite)

An Apple-inspired experiment viewer built as a static SPA and mounted on the A2E server at `:6006`. React connects directly to the `/v1/*` REST API without a `serve.py` middleware layer.

- **Swipe left or right** → Move between `Task / Trace / Eval` for the same sample
- **Trace panel** → Expand a sample to inspect its span tree
- **Eval panel** → Aggregate scores using `eval/metrics_catalog.json`

## Development

```bash
# 1. Start the A2E server
cd server && uv run a2e serve     # http://127.0.0.1:6006

# 2. Start the Vite dev server (proxy /v1 → :6006)
cd ui && pnpm install && pnpm dev   # http://127.0.0.1:5173
```

Alternatively, use `a2e serve --dev` with Vite HMR, which is already supported by the server templates.

## Production Build

```bash
cd ui && pnpm install && pnpm build
cd server && uv run a2e serve       # http://127.0.0.1:6006
```

Build artifacts are written to `ui/dist/`. The server reads `ui/dist/.vite/manifest.json`, with `index.tsx` as the entry point.

## Direct API Access

The frontend calls the server REST API directly from `src/api/`:

| Feature | REST |
|------|------|
| Experiment list | `GET /v1/datasets` + `GET /v1/datasets/{id}/experiments` |
| Sample records | `GET /v1/experiments/{id}/json` |
| Span tree | `GET /v1/projects/{project}/spans?trace_id=...` |
| Agent list | `GET /v1/a2e/registry` |
| Metrics catalog | Import `eval/metrics_catalog.json` at build time |

## Directory Structure

```
ui/
  src/           # React source code
  legacy/        # Legacy vanilla JS reference
  dist/          # pnpm build output (gitignored)
  public/        # Static assets (logos, etc.)
```

## Removal

```bash
rm -rf ui/
```

After removal, the A2E server API continues to run normally at `:6006`; only the web viewer is unavailable.
