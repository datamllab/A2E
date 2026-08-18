# Colab quickstart (public)

Open the demo notebook on the **public** repo [`datamllab/A2E`](https://github.com/datamllab/A2E) branch **`main`**.

**Colab link (anyone, no GitHub login required):**

https://colab.research.google.com/github/datamllab/A2E/blob/main/notebooks/a2e_quickstart.ipynb

Section **1. Live demo** is self-contained (embedded trajectories + CODE metrics). No `git clone`, no `GITHUB_TOKEN`, no OpenAI key.

## Run

1. Open the link above (or the Colab badge in README).
2. **Runtime → Run all**.
3. Optional sections (clone full repo, LLM metrics) are **off by default**.

## If the link still fails

| Symptom | Fix |
|---------|-----|
| **404** on `api.github.com/.../notebooks` | `notebooks/` not on `main` yet — repo maintainer runs `bash scripts/publish_colab_datamllab_main.sh` |
| Old notebook / *Clone failed* in Section 1 | Hard refresh; Section 1 must be *Live demo* (v2 standalone) |
| Optional clone (Section 3) fails | Set `CLONE_FULL_REPO=True` only with a PAT; public clone works without token |

## Fallback — upload (offline share)

```bash
bash scripts/package_colab_share.sh   # → dist/a2e_quickstart_colab.zip
```

Colab → **File → Upload notebook** → `a2e_quickstart.ipynb`.

## Publish checklist (maintainers)

After changing the notebook, push to **`datamllab/A2E` `main`**:

```bash
bash scripts/publish_colab_datamllab_main.sh
```

Verify (must return **200**):

```bash
curl -s -o /dev/null -w "%{http_code}\n" \
  "https://raw.githubusercontent.com/datamllab/A2E/main/notebooks/a2e_quickstart.ipynb"
```

(GitHub REST API may return **403** from rate limits; raw URL **200** is enough.)
