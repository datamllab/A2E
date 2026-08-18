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
  "https://api.github.com/repos/datamllab/A2E/contents/notebooks/a2e_quickstart.ipynb?ref=main"
```

---

# Colab 快速上手（公开仓库）

公开仓库 [`datamllab/A2E`](https://github.com/datamllab/A2E) 的 **`main`** 分支。

**Colab 链接（外部用户可直接打开，无需 GitHub 登录）：**

https://colab.research.google.com/github/datamllab/A2E/blob/main/notebooks/a2e_quickstart.ipynb

**第 1 节**自包含 demo，不需要 clone / token / OpenAI。

## 运行

1. 打开上方链接或 README 里的 Colab 徽章  
2. **运行时 → 全部运行**

## 仍然 404？

说明 `main` 上还没有 `notebooks/` — 维护者执行：

```bash
bash scripts/publish_colab_datamllab_main.sh
```

## 备用 — 上传 notebook

`bash scripts/package_colab_share.sh` 打 zip，Colab 里 **上传笔记本** 即可。
