"""A2E — Agent Evaluation Platform UI-trigger routes.

Endpoints exposed to the browser:

* ``GET  /v1/a2e/registry``     — list available datasets, agents, evaluators
* ``POST /v1/a2e/run-experiment`` — launch an A2E experiment in a background
  worker; returns immediately with a job id + experiment id.
* ``GET  /v1/a2e/jobs/{job_id}`` — poll job status
* ``GET  /a2e/run``             — self-contained HTML form (no React build
  required) that drives the two endpoints above; useful as an MVP page.

The handlers import ``ageneval.task.runners`` lazily so that this router
file can ship inside A2E without making A2E's task layer a hard dep.
"""

from __future__ import annotations

import asyncio
import logging
import os
import threading
import uuid
from typing import Any, Dict, List, Optional, Union

from fastapi import APIRouter, BackgroundTasks, HTTPException, Request
from fastapi.responses import HTMLResponse, JSONResponse
from pydantic import BaseModel

logger = logging.getLogger(__name__)


def _autoload_aep_env() -> None:
    """Load ``A2E/.env`` into ``os.environ`` so UI-triggered experiments have
    LLM credentials (``OPENAI_API_KEY`` / ``OPENAI_API_BASE`` / ``A2E_MODEL`` /
    ``ANTHROPIC_*``) even when ``a2e serve`` was started from a shell that
    never sourced the env file. Shell-exported variables win (``setdefault``).
    """
    from pathlib import Path

    for parent in Path(__file__).resolve().parents:
        # A2E repo root is the only ancestor with both a pyproject.toml and a
        # uv.lock; load the .env that sits beside them, if present.
        if (parent / "pyproject.toml").is_file() and (parent / "uv.lock").is_file():
            env_file = parent / ".env"
            if env_file.is_file():
                for raw in env_file.read_text(encoding="utf-8").splitlines():
                    line = raw.strip()
                    if not line or line.startswith("#") or "=" not in line:
                        continue
                    key, _, value = line.partition("=")
                    os.environ.setdefault(
                        key.strip(), value.strip().strip('"').strip("'")
                    )
                logger.info("A2E: loaded credentials from %s", env_file)
            return


_autoload_aep_env()

a2e_router = APIRouter(prefix="/v1/a2e", tags=["A2E"])


# ─── job table (in-memory; resets when A2E restarts) ──────────────────────


_jobs: Dict[str, Dict[str, Any]] = {}
_jobs_lock = threading.Lock()


def _new_job(meta: Dict[str, Any]) -> str:
    job_id = uuid.uuid4().hex[:12]
    with _jobs_lock:
        _jobs[job_id] = {"id": job_id, "status": "pending", **meta}
    return job_id


def _set_job(job_id: str, **patch: Any) -> None:
    with _jobs_lock:
        if job_id in _jobs:
            _jobs[job_id].update(patch)


# ─── request / response models ────────────────────────────────────────────────


class RunRequest(BaseModel):
    dataset: str
    agent: str
    evaluators: List[str]
    # Accept either a positive integer (e.g. 1, 50) or the literal "all" to
    # let the loader decide based on dataset size. The worker normalizes
    # "all" → None before invoking the loader.
    n: Union[int, str] = 1
    domain: Optional[str] = None
    model: Optional[str] = None
    api_base: Optional[str] = None
    api_key: Optional[str] = None


class RunResponse(BaseModel):
    job_id: str
    status: str
    detail: str


# ─── routes ───────────────────────────────────────────────────────────────────


@a2e_router.get("/registry")
def get_registry() -> JSONResponse:
    """Return the names of every dataset / agent / evaluator known to A2E."""
    try:
        from ageneval.task.runners import list_registries  # type: ignore
    except ImportError as exc:
        raise HTTPException(status_code=503, detail=f"task layer not installed: {exc}")
    return JSONResponse(list_registries())


@a2e_router.post("/run-experiment")
def run_experiment(req: RunRequest, background: BackgroundTasks) -> RunResponse:
    """Kick off an experiment in a background thread and return immediately."""
    try:
        from ageneval.task.runners import AGENTS, DATASETS  # type: ignore
    except ImportError as exc:
        raise HTTPException(status_code=503, detail=f"task layer not installed: {exc}")

    if req.dataset not in DATASETS:
        raise HTTPException(status_code=400, detail=f"unknown dataset: {req.dataset}")
    if req.agent not in AGENTS:
        raise HTTPException(status_code=400, detail=f"unknown agent: {req.agent}")
    if not req.evaluators:
        raise HTTPException(status_code=400, detail="at least one evaluator is required")

    job_id = _new_job(
        {
            "dataset": req.dataset,
            "agent": req.agent,
            "evaluators": req.evaluators,
            "n": req.n,
        }
    )
    background.add_task(_run_experiment_worker, job_id, req.model_dump())
    return RunResponse(job_id=job_id, status="pending", detail="Experiment dispatched")


@a2e_router.get("/jobs/{job_id}")
def get_job(job_id: str) -> JSONResponse:
    with _jobs_lock:
        if job_id not in _jobs:
            raise HTTPException(status_code=404, detail="unknown job")
        return JSONResponse(dict(_jobs[job_id]))


@a2e_router.get("/jobs")
def list_jobs() -> JSONResponse:
    with _jobs_lock:
        return JSONResponse({"jobs": list(_jobs.values())})


# ─── HTML form (no React build needed) ────────────────────────────────────────

# Mounted on the bare ``/a2e/run`` path so users can hit it without touching
# the existing UI. Tailwind-style flat tech look; no external CSS dep.

_HTML_PAGE = """<!DOCTYPE html>
<html lang="en"><head>
<meta charset="UTF-8" />
<title>A2E — Run Experiment</title>
<link rel="icon" href="/favicon.ico" type="image/x-icon" />
<link rel="preconnect" href="https://fonts.googleapis.com">
<link rel="preconnect" href="https://fonts.gstatic.com" crossorigin>
<link href="https://fonts.googleapis.com/css2?family=Geist:wght@300..700&family=Geist+Mono:wght@400..600&display=swap" rel="stylesheet">
<style>
  :root {
    --bg:#f6f8fb;
    --surface:#ffffff;
    --surface-soft:#f0f4fa;
    --border:#dde3ec;
    --text:#0f172a;
    --muted:#64748b;
    --accent:#2563eb;
    --accent-hi:#1d4ed8;
    --accent-soft:#dbeafe;
    --cyan:#06b6d4;
    --ok:#10b981;
    --warn:#f59e0b;
    --err:#ef4444;
    --shadow:0 1px 2px rgba(15,23,42,.04), 0 12px 30px rgba(37,99,235,.08);
  }
  * { box-sizing: border-box; }
  html, body { margin:0; padding:0; background:var(--bg); color:var(--text);
    font-family:"Geist","Inter","SF Pro Text",system-ui,sans-serif; min-height:100vh; }
  /* tech-feel gradient stripe at the top */
  body::before { content:""; position:fixed; top:0; left:0; right:0; height:3px;
    background:linear-gradient(90deg,var(--accent),var(--cyan),var(--accent)); z-index:99; }

  /* ───────────────── header / sidebar ───────────────── */
  .top-nav { background:var(--surface); border-bottom:1px solid var(--border);
    padding:14px 32px; display:flex; align-items:center; gap:20px;
    box-shadow:0 1px 0 rgba(15,23,42,.04); position:sticky; top:0; z-index:50; }
  .top-nav img { height:32px; }
  .top-nav .title { font-size:16px; font-weight:600; letter-spacing:.2px; }
  .top-nav .sub { font-size:11px; color:var(--muted); font-family:"Geist Mono",monospace;
    background:var(--accent-soft); color:var(--accent); padding:2px 8px; border-radius:999px;
    text-transform:uppercase; letter-spacing:.5px; }
  .top-nav .tabs { display:flex; gap:4px; margin-left:auto; }
  .top-nav .tab { font-size:13px; color:var(--muted); text-decoration:none;
    padding:8px 14px; border-radius:6px; transition:.15s; }
  .top-nav .tab:hover { background:var(--surface-soft); color:var(--text); }
  .top-nav .tab.active { background:var(--accent); color:white; }

  /* ───────────────── layout ───────────────── */
  main { max-width:1280px; margin:24px auto; padding:0 32px; display:grid;
    grid-template-columns: minmax(0,1.05fr) minmax(0,.95fr); gap:24px; }
  @media (max-width:1024px) { main { grid-template-columns:1fr; } }

  .card { background:var(--surface); border:1px solid var(--border); border-radius:12px;
    padding:24px 28px; margin-bottom:20px; box-shadow:var(--shadow); }
  .card h2 { font-size:11px; color:var(--accent); margin:0 0 18px 0;
    text-transform:uppercase; letter-spacing:1.5px; font-weight:700;
    display:flex; align-items:center; gap:8px; }
  .card h2::before { content:""; width:12px; height:2px; background:var(--accent);
    display:inline-block; border-radius:2px; }

  /* form rows */
  .row { display:grid; grid-template-columns:140px 1fr; gap:14px; align-items:center;
    margin-bottom:14px; }
  .row label { color:var(--muted); font-size:13px; font-weight:500; }
  select, input { width:100%; background:var(--surface); color:var(--text);
    border:1px solid var(--border); border-radius:8px; padding:9px 12px;
    font-family:inherit; font-size:13px; outline:none; transition:.15s; }
  select:focus, input:focus { border-color:var(--accent);
    box-shadow:0 0 0 3px rgba(37,99,235,.15); }
  input::placeholder { color:#94a3b8; }

  /* evaluator chip selector */
  .eval-controls { display:flex; align-items:center; gap:8px; margin-bottom:8px;
    font-size:11px; color:var(--muted); }
  .eval-controls button.mini { background:transparent; color:var(--accent);
    border:1px solid var(--border); padding:3px 10px; font-size:11px;
    font-weight:500; letter-spacing:.3px; }
  .eval-controls button.mini:hover { border-color:var(--accent); background:var(--accent-soft); }
  .checks { display:flex; flex-wrap:wrap; gap:8px; }
  .check { background:var(--surface); border:1px solid var(--border); border-radius:999px;
    padding:6px 14px; cursor:pointer; font-size:12px; font-family:"Geist Mono",monospace;
    user-select:none; transition:.15s; display:flex; align-items:center; gap:6px;
    color:var(--muted); }
  .check input { display:none; }
  .check::before { content:""; width:10px; height:10px; border:1.5px solid var(--border);
    border-radius:3px; display:inline-block; }
  .check.active { background:var(--accent-soft); color:var(--accent);
    border-color:var(--accent); font-weight:600; }
  .check.active::before { background:var(--accent); border-color:var(--accent);
    background-image: linear-gradient(45deg, transparent 40%, white 40% 60%, transparent 60%); }

  /* run button */
  .run-bar { display:flex; align-items:center; gap:14px; margin-top:20px;
    padding-top:18px; border-top:1px solid var(--border); }
  .run-bar .summary { flex:1; font-size:12px; color:var(--muted);
    font-family:"Geist Mono",monospace; }
  .run-bar .summary b { color:var(--accent); font-weight:600; }
  button.primary { background:var(--accent); color:white; border:none; border-radius:8px;
    padding:10px 24px; font-family:inherit; font-size:14px; font-weight:600;
    cursor:pointer; transition:.15s; letter-spacing:.3px; box-shadow:0 4px 12px rgba(37,99,235,.25); }
  button.primary:hover { background:var(--accent-hi); transform:translateY(-1px); }
  button.primary:disabled { background:var(--border); color:var(--muted);
    cursor:not-allowed; box-shadow:none; transform:none; }

  /* status panel */
  .status-head { display:flex; align-items:center; gap:10px; margin-bottom:14px; }
  .pill { display:inline-block; padding:3px 12px; border-radius:999px; font-size:11px;
    font-weight:600; text-transform:uppercase; letter-spacing:.5px;
    font-family:"Geist Mono",monospace; }
  .pill.idle { background:var(--surface-soft); color:var(--muted); }
  .pill.pending { background:#fef3c7; color:var(--warn); }
  .pill.running { background:var(--accent-soft); color:var(--accent); }
  .pill.done { background:#d1fae5; color:var(--ok); }
  .pill.error { background:#fee2e2; color:var(--err); }
  .log { background:var(--surface-soft); border:1px solid var(--border); border-radius:8px;
    padding:14px 16px; font-size:12px; font-family:"Geist Mono",monospace; line-height:1.6;
    max-height:380px; overflow:auto; white-space:pre-wrap; color:#1e293b; }
  .log .ts { color:var(--muted); }
  .log .ok { color:var(--ok); font-weight:600; }
  .log .err { color:var(--err); font-weight:600; }

  /* result links */
  .result-links { display:flex; gap:10px; margin-top:14px; flex-wrap:wrap; }
  .result-links a { display:inline-flex; align-items:center; gap:6px; padding:8px 16px;
    background:var(--accent); color:white; text-decoration:none; border-radius:8px;
    font-size:13px; font-weight:500; transition:.15s; box-shadow:0 2px 8px rgba(37,99,235,.18); }
  .result-links a:hover { background:var(--accent-hi); }
  .result-links a.secondary { background:var(--surface); color:var(--accent);
    border:1px solid var(--accent); box-shadow:none; }
  .result-links a.secondary:hover { background:var(--accent-soft); }

  /* helpful "why" footer */
  .info-box { font-size:12px; color:var(--muted); padding:14px 16px;
    background:var(--surface-soft); border:1px solid var(--border); border-radius:8px;
    line-height:1.6; font-family:"Geist Mono",monospace; margin-top:12px; }
  .info-box b { color:var(--accent); }
</style>
</head><body>
<nav class="top-nav">
  <img src="/ailab-logo.png" alt="Shanghai AI Lab" />
  <span class="title">A2E — Agent Evaluation Platform</span>
  <span class="sub">Run experiment</span>
  <span class="tabs">
    <a class="tab active" href="/a2e/run">▶ Run</a>
    <a class="tab" href="/datasets">Datasets</a>
    <a class="tab" href="/experiments">Experiments</a>
    <a class="tab" href="/projects">Projects</a>
  </span>
</nav>

<main>
  <!-- LEFT COLUMN — form -->
  <div>
    <div class="card">
      <h2>① Pick the combo</h2>
      <div class="row"><label>Dataset</label><select id="dataset"></select></div>
      <div class="row"><label>Agent framework</label><select id="agent"></select></div>
      <div class="row" style="align-items:start;">
        <label>Evaluators <span style="font-weight:400;font-size:11px;color:var(--muted);">(pick any)</span></label>
        <div>
          <div class="eval-controls">
            <button type="button" class="mini" id="eval-all">select all</button>
            <button type="button" class="mini" id="eval-none">clear</button>
            <span id="eval-count">0 selected</span>
          </div>
          <div id="evaluators" class="checks"></div>
        </div>
      </div>
      <div class="row"><label>n (examples)</label><input id="n" type="number" value="1" min="1" max="20" /></div>
      <div class="row"><label>Domain</label><input id="domain" placeholder="optional — retail / airline (for tau-bench / tau2)" /></div>
    </div>

    <div class="card">
      <h2>② LLM endpoint (optional)</h2>
      <div class="row"><label>Model</label><input id="model" value="qwen-plus" placeholder="e.g. qwen-plus, qwen-max (non-reasoning instruct model)" /></div>
      <div class="row"><label>OPENAI_API_BASE</label><input id="api_base" value="http://35.220.164.252:3888/v1/" placeholder="http://.../v1/" /></div>
      <div class="row"><label>OPENAI_API_KEY</label><input id="api_key" type="password" placeholder="sk-… (paste your key here)" /></div>
      <div class="info-box">
        Any OpenAI-compatible endpoint works for the <b>langgraph</b> agent.
        Leave model/base/key blank to use the server's process env
        (<b>OPENAI_API_BASE</b>, <b>OPENAI_API_KEY</b>, <b>A2E_LANGGRAPH_MODEL</b>).
      </div>
      <div id="claude-warn" class="info-box" style="display:none;background:#fef3c7;border-color:#fbbf24;color:#92400e;">
        <b>⚠ claude-sdk note</b>: this agent uses Anthropic's <code>claude-agent-sdk</code>
        which spawns the Claude Code CLI subprocess. It requires (a) the
        <code>claude</code> binary on PATH and (b) <code>ANTHROPIC_API_KEY</code> set on the
        a2e process — the OpenAI-compatible fields above are <b>not</b> used.
        For non-Anthropic endpoints, pick the <b>langgraph</b> agent.
      </div>
      <div id="isolated-warn" class="info-box" style="display:none;background:#fef3c7;border-color:#fbbf24;color:#92400e;">
        <b>⚠ isolated install</b>: <code id="isolated-name">this agent</code> lives in a
        separate sub-project with its own uv environment. Sync it first with
        <code>cd task/agents/<span id="isolated-path">…</span> &amp;&amp; uv sync</code>;
        otherwise the experiment fails with an import error.
      </div>
      <div class="run-bar">
        <div class="summary" id="summary">…</div>
        <button class="primary" id="run">▶ Run Experiment</button>
      </div>
    </div>
  </div>

  <!-- RIGHT COLUMN — live status -->
  <div>
    <div class="card">
      <div class="status-head">
        <h2 style="margin:0;">Live progress</h2>
        <span id="status-pill" class="pill idle">idle</span>
      </div>
      <div id="log" class="log">Waiting for a run… pick a combo on the left and click Run.</div>
      <div class="result-links" id="result-links" style="display:none;"></div>
    </div>

    <div class="card">
      <h2>How A2E pages relate</h2>
      <div class="info-box" style="margin-top:0;">
        <b>Run</b> (here) — pick dataset × agent × evaluators, launch a job.<br>
        <b>Datasets</b> — every dataset uploaded (tau-bench, mmlu, …).<br>
        <b>Experiments</b> — past runs, per-example scores, evaluator breakdown.<br>
        <b>Projects</b> — raw OpenTelemetry traces (agent's full LLM + tool tree).<br>
        After Run finishes you'll get one-click jumps to the right page.
      </div>
    </div>
  </div>
</main>

<script>
const $ = (id) => document.getElementById(id);
let currentJob = null;
let pollHandle = null;
const DEFAULT_ACTIVE = new Set(["exact_match","substring","llm_judge"]);

function updateSummary() {
  const ds = $("dataset").value || "?";
  const ag = $("agent").value || "?";
  const ev = Array.from(document.querySelectorAll('#evaluators .check.active')).map(e => e.dataset.name);
  $("eval-count").textContent = ev.length + " selected";
  $("summary").innerHTML = `<b>${ds}</b> × <b>${ag}</b> × <b>${ev.length || '(none)'}</b> eval(s)`;
  $("run").disabled = ev.length === 0;
}

// Fixed render order for the agent <optgroup> labels — must match the
// React A2ERunPage taxonomy.
const AGENT_GROUP_ORDER = [
  "Agent-first frameworks",
  "Orchestration frameworks",
  "Vendor agent SDKs",
];
let AGENT_META = {};
let DATASET_META = {};

// Pre-select the recommended evaluators for the chosen dataset (tool datasets
// → trajectory + answer-quality metrics, QA → the metric for their answer
// style). Mirrors `default_evaluators` in registry.py and the React launcher.
function applyDatasetDefaults() {
  const ds = $("dataset").value;
  const defaults = (DATASET_META[ds] && DATASET_META[ds].default_evaluators) || [];
  if (!defaults.length) return;
  const want = new Set(defaults);
  document.querySelectorAll('#evaluators .check').forEach((l) => {
    const on = want.has(l.dataset.name);
    l.classList.toggle('active', on);
    const cb = l.querySelector('input');
    if (cb) cb.checked = on;
  });
  updateSummary();
}

function syncAgentWarnings() {
  const a = $("agent").value;
  $("claude-warn").style.display = (a === "claude-sdk") ? "block" : "none";
  const isolated = !!(AGENT_META[a] && AGENT_META[a].isolated);
  $("isolated-warn").style.display = isolated ? "block" : "none";
  if (isolated) {
    $("isolated-name").textContent = a;
    $("isolated-path").textContent = a;
  }
}

async function loadRegistry() {
  const r = await fetch("/v1/a2e/registry").then((x) => x.json());
  AGENT_META = r.agent_meta || {};
  DATASET_META = r.dataset_meta || {};
  const dsel = $("dataset");
  r.datasets.forEach((d) => { const o = document.createElement("option"); o.value = o.text = d; dsel.appendChild(o); });
  const asel = $("agent");
  // Group agents by `agent_meta[a].group`; fixed group order; sort within
  // each group by name; skip empty groups. Agents lacking metadata fall
  // back to the first group.
  const groups = {};
  AGENT_GROUP_ORDER.forEach((g) => { groups[g] = []; });
  r.agents.forEach((a) => {
    const g = (AGENT_META[a] && AGENT_META[a].group) || AGENT_GROUP_ORDER[0];
    (groups[g] = groups[g] || []).push(a);
  });
  const orderedLabels = AGENT_GROUP_ORDER.concat(
    Object.keys(groups).filter((g) => AGENT_GROUP_ORDER.indexOf(g) === -1)
  );
  orderedLabels.forEach((label) => {
    const items = groups[label] || [];
    if (!items.length) return;
    const og = document.createElement("optgroup");
    og.label = label;
    items.slice().sort((x, y) => x.localeCompare(y)).forEach((a) => {
      const o = document.createElement("option");
      o.value = o.text = a;
      og.appendChild(o);
    });
    asel.appendChild(og);
  });
  const ec = $("evaluators");
  r.evaluators.forEach((e) => {
    const lbl = document.createElement("label"); lbl.className = "check"; lbl.dataset.name = e;
    const cb = document.createElement("input"); cb.type = "checkbox"; cb.value = e;
    lbl.appendChild(cb);
    lbl.appendChild(document.createTextNode(e));
    lbl.onclick = (ev) => {
      ev.preventDefault();
      lbl.classList.toggle("active");
      cb.checked = lbl.classList.contains("active");
      updateSummary();
    };
    if (DEFAULT_ACTIVE.has(e)) { lbl.classList.add("active"); cb.checked = true; }
    ec.appendChild(lbl);
  });
  $("dataset").onchange = () => { applyDatasetDefaults(); updateSummary(); };
  $("agent").onchange = () => { syncAgentWarnings(); updateSummary(); };
  // initial warning state + recommended evaluators for the first dataset
  syncAgentWarnings();
  applyDatasetDefaults();
  $("eval-all").onclick = () => {
    document.querySelectorAll('#evaluators .check').forEach((l) => l.classList.add('active'));
    updateSummary();
  };
  $("eval-none").onclick = () => {
    document.querySelectorAll('#evaluators .check').forEach((l) => l.classList.remove('active'));
    updateSummary();
  };
  updateSummary();
}

function appendLog(text, cls) {
  const t = new Date().toLocaleTimeString();
  const log = $("log");
  const cleanLine = "\\n" + `<span class=\\"ts\\">[${t}]</span> `;
  if (cls) {
    log.innerHTML += cleanLine + `<span class=\\"${cls}\\">${text}</span>`;
  } else {
    log.innerHTML += cleanLine + text;
  }
  log.scrollTop = log.scrollHeight;
}

function setStatus(name) {
  const p = $("status-pill");
  p.className = "pill " + (name || "idle");
  p.textContent = name || "idle";
}

async function startRun() {
  const evaluators = Array.from(document.querySelectorAll('#evaluators .check.active'))
    .map((el) => el.dataset.name);
  if (!evaluators.length) {
    appendLog("✗ pick at least one evaluator", "err");
    return;
  }
  const payload = {
    dataset: $("dataset").value, agent: $("agent").value, evaluators,
    n: parseInt($("n").value || "1", 10),
    domain: $("domain").value || null, model: $("model").value || null,
    api_base: $("api_base").value || null, api_key: $("api_key").value || null,
  };
  $("log").innerHTML = "<span class=\\"ts\\">→</span> POST /v1/a2e/run-experiment\\n" + JSON.stringify(payload, null, 2);
  $("run").disabled = true;
  $("result-links").style.display = "none";
  setStatus("pending");
  try {
    const r = await fetch("/v1/a2e/run-experiment", {
      method: "POST", headers: {"Content-Type": "application/json"},
      body: JSON.stringify(payload),
    });
    const j = await r.json();
    if (!r.ok) throw new Error(j.detail || r.statusText);
    currentJob = j.job_id;
    appendLog("← job " + j.job_id + " — " + j.detail);
    appendLog("polling every 2s…");
    pollHandle = setInterval(pollJob, 2000);
  } catch (e) {
    setStatus("error");
    appendLog("✗ " + e.message, "err");
    $("run").disabled = false;
  }
}

async function pollJob() {
  if (!currentJob) return;
  const j = await fetch("/v1/a2e/jobs/" + currentJob).then((x) => x.json());
  setStatus(j.status);
  if (j.message && j.message !== window._last_msg) {
    window._last_msg = j.message;
    appendLog(j.message);
  }
  if (j.status === "done" || j.status === "error") {
    clearInterval(pollHandle); $("run").disabled = false;
    if (j.status === "done") {
      appendLog("✓ experiment finished", "ok");
      const rl = $("result-links");
      rl.innerHTML = "";
      rl.style.display = "flex";
      if (j.experiment_url) {
        const a = document.createElement("a");
        a.href = j.experiment_url;
        a.textContent = "→ View experiment scores";
        rl.appendChild(a);
      }
      const a2 = document.createElement("a");
      a2.href = "/datasets"; a2.className = "secondary";
      a2.textContent = "Datasets";
      rl.appendChild(a2);
      const a3 = document.createElement("a");
      a3.href = "/projects"; a3.className = "secondary";
      a3.textContent = "Trace tree (Projects)";
      rl.appendChild(a3);
    } else {
      appendLog("✗ " + (j.message || "error"), "err");
    }
  }
}

$("run").onclick = startRun;
loadRegistry();
</script>
</body></html>
"""


@a2e_router.get("/", include_in_schema=False)
def aep_root() -> JSONResponse:
    """Tiny welcome JSON; the real entry is GET /a2e/run (served by app.py)."""
    return JSONResponse({"name": "A2E", "ui": "/a2e/run"})


def a2e_html_page() -> HTMLResponse:
    return HTMLResponse(_HTML_PAGE)


# ─── background worker ────────────────────────────────────────────────────────


def _run_experiment_worker(job_id: str, payload: Dict[str, Any]) -> None:
    """Runs the experiment to completion inside a worker thread."""
    from ageneval.task.core import setup_instrumentation, TaskInput  # type: ignore
    from ageneval.task.runners import (  # type: ignore
        AGENTS,
        DATASETS,
        framework_for_agent,
        make_llm_judge,
        EVALUATORS,
    )

    try:
        # Preflight: catch obvious agent × env mismatches early.
        if payload["agent"] == "claude-sdk" and not os.environ.get("ANTHROPIC_API_KEY"):
            _set_job(
                job_id,
                status="error",
                message=(
                    "claude-sdk requires ANTHROPIC_API_KEY on the a2e server process, "
                    "plus the `claude` CLI binary on PATH. For OpenAI-compatible / Deepseek "
                    "endpoints, switch the agent to `langgraph` instead."
                ),
            )
            return

        _set_job(job_id, status="running", message="setting up instrumentation")

        framework = framework_for_agent(payload["agent"])
        provider = setup_instrumentation(
            project_name=f"a2e-{payload['dataset']}-{payload['agent']}",
            framework=framework,
        )

        # Load dataset + binding
        ds_entry = DATASETS[payload["dataset"]]
        # Normalize n: accept int, "all", or numeric strings; "all" → None
        # (let the loader return its full default split).
        _raw_n = payload.get("n", 1)
        if isinstance(_raw_n, str):
            _raw_n_stripped = _raw_n.strip().lower()
            n_value: Optional[int]
            if _raw_n_stripped in ("all", "*", ""):
                n_value = None
            else:
                try:
                    n_value = int(_raw_n_stripped)
                except ValueError:
                    n_value = 1
        else:
            n_value = int(_raw_n) if _raw_n is not None else None
        load_kwargs: Dict[str, Any] = {"n": n_value}
        bind_kwargs: Dict[str, Any] = {}
        if payload["dataset"] in ("tau-bench", "tau2") and payload.get("domain"):
            load_kwargs["domain"] = payload["domain"]
            bind_kwargs["domain"] = payload["domain"]
        dataset = ds_entry["load"](**load_kwargs)
        binding = ds_entry["bind"](**bind_kwargs)
        _set_job(job_id, message=f"loaded dataset: {dataset.name} ({len(dataset)} tasks)")

        # Build agent with env override for API base/key
        agent_kwargs: Dict[str, Any] = {"binding": binding}
        if payload.get("model"):
            agent_kwargs["model"] = payload["model"]
        for env_key, override in [("OPENAI_API_BASE", "api_base"), ("OPENAI_API_KEY", "api_key")]:
            if payload.get(override):
                os.environ[env_key] = payload[override]
                agent_kwargs[override] = payload[override]
        agent = AGENTS[payload["agent"]]["build"](**agent_kwargs)
        _set_job(job_id, message=f"agent ready: {agent.name}")

        # Upload dataset to a2e
        from a2e.client import Client  # type: ignore

        client = Client()
        # Include the task count in the A2E dataset name so a different N
        # produces a distinct dataset instead of silently reusing an older,
        # smaller one (which would cap runCount below the requested N).
        ds_name = f"a2e-{dataset.name}-n{len(dataset)}"
        examples = [
            {
                "input": {"instruction": t.instruction, "initial_state": dict(t.initial_state)},
                "output": {
                    "expected_outputs": list(t.expected_outputs),
                    "expected_actions": list(t.expected_actions),
                },
                "metadata": {"task_id": t.task_id, **dict(t.metadata)},
            }
            for t in dataset.tasks
        ]
        try:
            a2e_dataset = client.datasets.create_dataset(
                name=ds_name,
                examples=examples,
                dataset_description=f"A2E via UI: {dataset.name}",
            )
        except Exception:
            a2e_dataset = client.datasets.get_dataset(dataset=ds_name)
        _set_job(job_id, message=f"A2E dataset ready: {ds_name}")

        # Build evaluators
        judge_llm = None
        if "llm_judge" in payload["evaluators"]:
            try:
                from a2e.evals.llm import LLM  # type: ignore

                judge_kwargs: Dict[str, Any] = {
                    "provider": "openai",
                    "model": payload.get("model")
                    or os.environ.get("A2E_MODEL")
                    or os.environ.get("A2E_LANGGRAPH_MODEL")
                    or "qwen-plus",
                }
                if payload.get("api_base") or os.environ.get("OPENAI_API_BASE"):
                    judge_kwargs["base_url"] = payload.get("api_base") or os.environ["OPENAI_API_BASE"]
                if payload.get("api_key") or os.environ.get("OPENAI_API_KEY"):
                    judge_kwargs["api_key"] = payload.get("api_key") or os.environ["OPENAI_API_KEY"]
                judge_llm = LLM(**judge_kwargs)
            except Exception as exc:  # noqa: BLE001
                logger.warning("LLM judge build failed: %s", exc)

        evaluators: list = []
        for name in payload["evaluators"]:
            if name == "llm_judge":
                if judge_llm is not None:
                    evaluators.append(make_llm_judge(judge_llm))
            elif name in EVALUATORS:
                evaluators.append(EVALUATORS[name])

        # Task fn
        def task_fn(input: dict, metadata: dict) -> dict:
            t = TaskInput(
                task_id=metadata.get("task_id", "?"),
                instruction=input.get("instruction", ""),
                initial_state=input.get("initial_state", {}),
            )
            trace = asyncio.run(agent.run(t))
            return {
                "final_answer": trace.final_answer or "",
                "tool_calls": [tc.name for tc in trace.tool_calls],
                "status": trace.status,
                "turns": trace.turns,
                "trace_id": trace.trace_id,
                "error": trace.error,
            }

        from a2e.client.experiments import run_experiment as a2e_run_experiment  # type: ignore

        _set_job(job_id, message="running experiment …")
        ran = a2e_run_experiment(
            dataset=a2e_dataset,
            task=task_fn,
            evaluators=evaluators,
            experiment_name=f"{payload['dataset']}-{payload['agent']}",
        )
        # ``RanExperiment`` is a TypedDict — read the keys directly so we
        # produce a deep-link to the experiment-compare page.
        exp_id = (ran.get("experiment_id") if isinstance(ran, dict) else None) or ""
        ds_id = (
            (ran.get("dataset_id") if isinstance(ran, dict) else None)
            or getattr(a2e_dataset, "id", None)
            or ""
        )
        if ds_id and exp_id:
            url = f"/datasets/{ds_id}/compare?experimentId={exp_id}"
        elif ds_id:
            url = f"/datasets/{ds_id}/experiments"
        else:
            url = "/experiments"

        provider.force_flush(timeout_millis=5000)
        _set_job(
            job_id,
            status="done",
            message=f"experiment finished — open {url}",
            experiment_url=url,
        )
    except Exception as exc:  # noqa: BLE001
        logger.exception("A2E run-experiment worker failed")
        raw = f"{type(exc).__name__}: {exc}"
        hint = ""
        if "ProcessError" in raw or "claude-agent-sdk" in raw or "Command failed" in raw:
            hint = (
                "  Hint: claude-agent-sdk failed to spawn its Claude Code CLI subprocess. "
                "Ensure the `claude` binary is installed AND ANTHROPIC_API_KEY is set on the "
                "a2e server process. For OpenAI-compatible / Deepseek endpoints, switch "
                "the agent to `langgraph` instead."
            )
        elif "datasets" in raw and "huggingface" in raw.lower():
            hint = (
                "  Hint: HuggingFace download failed. Check internet to huggingface.co or "
                "pre-cache the dataset with `huggingface-cli download <id>`."
            )
        elif "openai" in raw.lower() and ("api_key" in raw.lower() or "auth" in raw.lower()):
            hint = (
                "  Hint: LLM auth failed. Verify OPENAI_API_KEY and OPENAI_API_BASE point at "
                "a reachable endpoint."
            )
        _set_job(job_id, status="error", message=(raw + ("\n" + hint if hint else ""))[:1200])
