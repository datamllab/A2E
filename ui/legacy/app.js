/* ui — Apple-flavored throwaway viewer.
   Task   = interactive benchmark tree (click a benchmark to load it)
   Trace  = one sample at a time (vertical swipe): instruction, metrics,
            expected output, and the real span tree
   Eval   = average results across all samples of the selected benchmark
   Horizontal deck (Task/Trace/Eval) uses a coverflow peek. Vanilla JS. */

const $ = (sel, root = document) => root.querySelector(sel);
const el = (tag, cls, html) => {
  const n = document.createElement(tag);
  if (cls) n.className = cls;
  if (html != null) n.innerHTML = html;
  return n;
};
const esc = (s) =>
  String(s ?? "").replace(
    /[&<>"]/g,
    (c) => ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;" })[c],
  );
const pretty = (v) => {
  try {
    return typeof v === "string" ? v : JSON.stringify(v, null, 2);
  } catch {
    return String(v);
  }
};

const deck = $("#deck");
const dotsEl = $("#dots");
const segmented = $("#segmented");
const segTrack = $("#seg-track");
const counterEl = $("#counter");
const toastEl = $("#toast");
const overlay = $("#overlay");
const overlayMsg = $("#overlay-msg");
const spinner = $("#spinner");
const retry = $("#retry");

let activePanel = 0;
let activeSample = 0;
let currentExperiment = null; // selected experiment (carries project_name)
let currentRecords = [];
let currentBenchmark = null;
let currentAgent = null;
let currentModel = "gpt-5.5";
let allExperiments = [];
let allAgents = [];
let metricsCatalog = null; // eval/metrics_catalog.json, loaded at boot
let traceBraceObserver = null;
const MODEL_OPTIONS = ["gpt-5.5", "gpt-4.1", "claude-3.7-sonnet", "qwen-max"];
const AGENT_FALLBACK = [
  { id: "agno", label: "Agno", aliases: [] },
  { id: "anthropic", label: "Anthropic", aliases: [] },
  { id: "autogen-agentchat", label: "AutoGen", aliases: ["autogen", "autogen_agentchat"] },
  { id: "claude-agent-sdk", label: "Claude SDK", aliases: ["claude-sdk", "claude_sdk", "claudesdk"] },
  { id: "crewai", label: "CrewAI", aliases: [] },
  { id: "google-adk", label: "Google ADK", aliases: ["google_adk"] },
  { id: "langchain", label: "LangChain / LangGraph", aliases: ["langgraph", "lang_chain"] },
  { id: "llama-index", label: "LlamaIndex", aliases: ["llama_index"] },
  { id: "openai", label: "OpenAI", aliases: [] },
  { id: "openai-agents", label: "OpenAI Agents", aliases: ["openai_agents"] },
  { id: "smolagents", label: "Smolagents", aliases: [] },
];

/* ─────────────────────────── benchmark tree data ─────────────────────────── */
// columns
const CATS = ["Coding", "Conversational", "Research", "Computer use"];
const CAPS = ["Skill", "Memory", "Tool"];
const YEARS = ["2020", "2021", "2022", "2023", "2024", "2025", "2026"];
// difficulty class: found / med / hard / front
// `key` (optional) is matched against dataset names to wire up real data.
// `dim`: 0 = Skill, 1 = Memory, 2 = Tool.
const BENCHMARKS = [
  // Coding
  { name: "HumanEval", cat: 0, year: "2021", diff: "found", key: "humaneval" },
  { name: "SWE-bench Lite", cat: 0, year: "2024", diff: "hard", dim: 2, key: "swe-bench-lite" },
  { name: "SWE-bench Verified", cat: 0, year: "2024", diff: "hard", dim: 2, key: "swe-bench-verified" },
  { name: "SWE-bench Pro", cat: 0, year: "2025", diff: "front", dim: 2, key: "swe-bench-pro" },

  // Skill
  { name: "SkillsBench", year: "2026", date: "2026-02-13", diff: "front", dim: 0 },
  { name: "SkillCraft", year: "2026", date: "2026-02-28", diff: "front", dim: 0 },
  { name: "SWE-Skills-Bench", year: "2026", date: "2026-03-16", diff: "front", dim: 0 },
  { name: "SkillTester", year: "2026", date: "2026-03-28", diff: "front", dim: 0 },
  { name: "SkillSafetyBench", year: "2026", date: "2026-05-12", diff: "front", dim: 0 },

  // Memory
  { name: "LoCoMo", year: "2024", date: "2024-02-27", diff: "hard", dim: 1 },
  { name: "LongMemEval", year: "2024", date: "2024-10-14", diff: "hard", dim: 1 },
  { name: "MemoryAgentBench", year: "2025", date: "2025-07-07", diff: "front", dim: 1 },
  { name: "EvoMemBench", year: "2026", date: "2026-05-18", diff: "front", dim: 1 },
  { name: "MemGym", year: "2026", date: "2026-05-20", diff: "front", dim: 1 },

  // Tool / interactive service workflow
  { name: "τ-bench", cat: 1, year: "2024", diff: "hard", dim: 2, key: "tau-bench" },
  { name: "τ²-bench", cat: 1, year: "2025", diff: "front", dim: 2, key: "tau2" },
  { name: "τ³-bench", cat: 1, year: "2025", diff: "front", dim: 2, key: "tau3" },

  // Research
  { name: "GAIA", cat: 2, year: "2023", diff: "med" },
  { name: "GPQA", cat: 2, year: "2023", diff: "hard" },
  { name: "AssistantBench", cat: 2, year: "2024", diff: "hard", dim: 2 },
  { name: "BrowseComp", cat: 2, year: "2025", diff: "front", dim: 2 },
  { name: "Humanity's Last Exam", cat: 2, year: "2025", diff: "front" },

  // Computer use
  { name: "WebShop", cat: 3, year: "2022", diff: "med", dim: 2 },
  { name: "WebArena", cat: 3, year: "2023", diff: "hard", dim: 2 },
  { name: "OSWorld", cat: 3, year: "2024", diff: "hard", dim: 2 },
  { name: "AndroidWorld", cat: 3, year: "2024", diff: "med", dim: 2 },
  { name: "TheAgentCompany", cat: 3, year: "2025", diff: "front" },
];
const DIFF_LABEL = {
  found: ["Foundational", "#8e8e93"],
  med: ["Medium", "#2bc0a8"],
  hard: ["Hard", "#ff9f0a"],
  front: ["Frontier", "#ff375f"],
};
const TREE_FACES = [
  { title: "Domain × Year", cols: CATS, colOf: (b) => b.cat },
  { title: "Capability Dimension · Skill / Memory / Tool", cols: CAPS, colOf: (b) => b.dim },
];
const BENCH_FACES = [
  { id: "overview", title: "Benchmark Map", sub: "Task family × release year", type: "grid" },
  {
    id: "skill",
    title: "Skill & Memory",
    sub: "Reusable skills and long-term memory",
    type: "cards",
    groups: [
      {
        label: "Skill",
        items: [
          { name: "SkillsBench", year: "2026", note: "skill utility across domains", diff: "front" },
          { name: "SkillCraft", year: "2026", note: "staged skill-construction suite", diff: "front" },
          { name: "SWE-Skills-Bench", year: "2026", note: "skill impact in real-world SWE", diff: "front" },
          { name: "SkillTester", year: "2026", note: "utility and security QA", diff: "front" },
          { name: "SkillSafetyBench", year: "2026", note: "skill safety and misuse resistance", diff: "front" },
        ],
      },
      {
        label: "Memory",
        items: [
          { name: "LoCoMo", year: "2024", note: "very long-term conversation memory", diff: "hard" },
          { name: "LongMemEval", year: "2024", note: "long-term interactive memory", diff: "hard" },
          { name: "MemoryAgentBench", year: "2025", note: "retrieval, learning, forgetting", diff: "hard" },
          { name: "EvoMemBench", year: "2026", note: "self-evolving agent memory", diff: "front" },
          { name: "MemGym", year: "2026", note: "long-horizon memory environment", diff: "front" },
        ],
      },
    ],
  },
];

/* ─────────────────────────── boot ─────────────────────────── */
async function load() {
  showOverlay("Loading benchmarks…", true);
  try {
    const [expRes, agentData] = await Promise.all([fetch("/api/experiments"), loadAgents()]);
    const expData = await expRes.json();
    if (!expRes.ok) throw new Error(expData.error || expRes.statusText);
    metricsCatalog = await loadMetricsCatalog();
    allAgents = agentData.agents || [];
    allExperiments = expData.experiments || [];
    buildDeck(allExperiments, allAgents);
    await loadDefaultSelection(allExperiments, allAgents);
    hideOverlay();
  } catch (e) {
    showError(e.message || String(e));
  }
}

async function loadAgents() {
  try {
    const res = await fetch("/api/agents");
    const data = await res.json();
    if (!res.ok) throw new Error(data.error || res.statusText);
    return data;
  } catch {
    return { agents: AGENT_FALLBACK };
  }
}

async function loadMetricsCatalog() {
  try {
    const res = await fetch("/api/metrics-catalog");
    return res.ok ? await res.json() : null;
  } catch {
    return null;
  }
}

/* Metric names of a catalog group (searches both process_values / result_values).
   Returns [] when the catalog is unavailable so callers can fall back. */
function catalogGroupMetrics(group) {
  const cats = metricsCatalog?.categories || {};
  for (const top of Object.values(cats)) {
    const g = top?.groups?.[group];
    if (g) return (g.metrics || []).map((m) => m.name);
  }
  return [];
}

function buildDeck(experiments, agents = []) {
  deck.innerHTML = "";
  deck.append(benchPanel(experiments, agents));
  deck.append(tracePanel());
  deck.append(evalPanel());

  deck.addEventListener(
    "scroll",
    () => {
      paintPeek(deck);
      updateSeg(); // segmented thumb follows the scroll continuously
    },
    { passive: true },
  );
  // Trace's internal vertical pager → highlight the sample nearest the top
  $("#trace-vpager").addEventListener(
    "scroll",
    () => {
      const idx = activeCardIndex();
      if (idx < 0 || idx === activeSample) return;
      activeSample = idx;
      paintDots();
      updateCounter();
    },
    { passive: true },
  );

  requestAnimationFrame(() => {
    setPanel(0, true);
    paintPeek(deck);
  });
}

/* ─────────────────────────── Task: benchmark tree ─────────────────────────── */
function normKey(s) {
  return String(s || "").toLowerCase().replace(/[^a-z0-9]/g, "");
}

function benchKey(b) {
  return b.key || b.name;
}

function benchFamily(b) {
  return CATS[b.cat] || CAPS[b.dim] || "Benchmark";
}

function benchExperiments(b, experiments) {
  const key = normKey(benchKey(b));
  if (!key) return [];
  return experiments.filter((e) => {
    const haystack = normKey(`${e.dataset_name || ""} ${e.name || ""}`);
    return haystack.includes(key);
  });
}

function agentTokens(agent) {
  return [agent.id, agent.label, ...(agent.aliases || [])].map(normKey).filter(Boolean);
}

function findAgentExperiment(experiments, agent) {
  if (agent.id === "claude-agent-sdk") return experiments[0];
  const tokens = agentTokens(agent);
  return experiments.find((e) => {
    const haystack = normKey(`${e.name || ""} ${e.project_name || ""} ${e.dataset_name || ""}`);
    return tokens.some((t) => haystack.includes(t));
  });
}

function defaultSelection(experiments, agents) {
  for (const b of BENCHMARKS) {
    const sel = benchDefaultSelection(b, experiments, agents);
    if (sel) return sel;
  }
  return null;
}

function benchDefaultSelection(b, experiments, agents) {
  const exps = benchExperiments(b, experiments);
  if (!exps.length) return null;
  for (const agent of agents) {
    const exp = findAgentExperiment(exps, agent);
    if (exp) return { b, exp, agent };
  }
  return { b, exp: exps[0], agent: null };
}

async function loadDefaultSelection(experiments, agents) {
  const sel = defaultSelection(experiments, agents);
  if (!sel) return;
  markBenchSelected(sel.b);
  await selectBenchmark(sel.b, sel.exp, sel.agent, { navigate: false, announce: false });
}

function markBenchSelected(b) {
  deck.querySelectorAll(".bench-chip.sel").forEach((c) => c.classList.remove("sel"));
  const key = normKey(benchKey(b));
  const chip = [...deck.querySelectorAll(".bench-chip")].find((c) => c.dataset.benchKey === key);
  if (chip) chip.classList.add("sel");
}

function benchPanel(experiments, agents) {
  const findExp = (b) => benchExperiments(b, experiments)[0];

  const panel = el("article", "panel bench");
  const inner = el("div", "panel-inner");
  inner.append(el("p", "kicker", "Task"));
  inner.append(el("h2", "bench-title", "Agent benchmark tree"));

  // diagnostic: what got linked
  const linked = BENCHMARKS.filter((b) => findExp(b)).map((b) => b.name);
  const diag = el(
    "p",
    "muted",
    `Connected to ${experiments.length} experiments` +
      (linked.length ? ` · Data available: ${esc(linked.join(", "))}` : " · No matching benchmarks"),
  );
  diag.style.cssText = "margin:-4px 0 4px;font-size:12px";
  inner.append(diag);

  const ctrl = el("div", "cube-ctrl");
  const faceTitle = el("span", "cube-face-title", esc(TREE_FACES[0].title));
  const flipBtn = el("button", "cube-flip", "Rotate ↻");
  ctrl.append(faceTitle, flipBtn);
  inner.append(ctrl);

  const scene = el("div", "cube-scene");
  const cube = el("div", "cube");
  const faces = TREE_FACES.map((face) => {
    const faceEl = el("div", "cube-face");
    faceEl.append(benchGrid(face, experiments, agents));
    cube.append(faceEl);
    return faceEl;
  });
  scene.append(cube);
  inner.append(scene);
  setupCube(scene, cube, faces, faceTitle, flipBtn);

  const legend = el("div", "bench-legend");
  Object.values(DIFF_LABEL).forEach(([label, color]) => {
    const s = el("span");
    const i = el("i");
    i.style.background = color;
    s.append(i, document.createTextNode(label));
    legend.append(s);
  });
  inner.append(legend);

  panel.append(inner);
  return panel;
}

function benchGrid(face, experiments, agents) {
  const wrap = el("div", "bench-wrap");
  const grid = el("div", "bench-grid");
  grid.style.gridTemplateColumns = `44px repeat(${face.cols.length}, minmax(120px, 1fr))`;
  grid.append(el("div", ""));
  face.cols.forEach((c) => grid.append(el("div", "bench-cat", esc(c))));

  YEARS.forEach((y) => {
    grid.append(el("div", "bench-year", esc(y)));
    face.cols.forEach((_, ci) => {
      const cell = el("div", "bench-cell");
      BENCHMARKS.filter((b) => face.colOf(b) === ci && b.year === y).forEach((b) => {
        const exps = benchExperiments(b, experiments);
        cell.append(benchChip(b, exps, agents));
      });
      grid.append(cell);
    });
  });
  wrap.append(grid);
  return wrap;
}

function setupCube(scene, cube, faces, faceTitle, flipBtn) {
  const n = faces.length;
  const step = 360 / n;
  const D = 360;
  faces.forEach((face, i) => {
    face.style.transform = `rotateY(${i * step}deg) translateZ(${D}px)`;
  });

  let angle = 0;
  let dragX = null;
  let base = 0;
  let moved = 0;

  const apply = () => {
    cube.style.transform = `translateZ(-${D}px) rotateY(${angle}deg)`;
  };
  const frontIndex = () => ((Math.round(-angle / step) % n) + n) % n;
  const refreshLabel = () => {
    const idx = frontIndex();
    faceTitle.textContent = TREE_FACES[idx].title;
    faces.forEach((f, i) => f.classList.toggle("front", i === idx));
  };
  const snap = () => {
    angle = Math.round(angle / step) * step;
    cube.style.transition = "";
    apply();
    refreshLabel();
  };
  const fit = () => {
    const h = Math.max(...faces.map((f) => f.scrollHeight), 240);
    scene.style.height = h + "px";
  };

  flipBtn.addEventListener("click", () => {
    angle -= step;
    cube.style.transition = "";
    apply();
    refreshLabel();
  });
  scene.addEventListener("pointerdown", (e) => {
    dragX = e.clientX;
    base = angle;
    moved = 0;
    cube.style.transition = "none";
  });
  window.addEventListener("pointermove", (e) => {
    if (dragX == null) return;
    moved = e.clientX - dragX;
    angle = base + moved * 0.35;
    apply();
  });
  window.addEventListener("pointerup", () => {
    if (dragX == null) return;
    dragX = null;
    if (Math.abs(moved) < 4) {
      cube.style.transition = "";
      return;
    }
    snap();
  });

  apply();
  refreshLabel();
  requestAnimationFrame(fit);
  window.addEventListener("resize", fit);
}

function benchChip(b, exps, agents) {
  const chipText = `<span class="bench-name">${esc(b.name)}</span>${b.date ? `<span class="bench-date">${esc(b.date)}</span>` : ""}`;
  const chip = el(
    "button",
    `bench-chip d-${b.diff}${exps.length ? " avail" : ""}`,
    chipText,
  );
  chip.dataset.benchKey = normKey(benchKey(b));
  if (b.date) chip.title = `${b.name} · released ${b.date}`;
  chip.addEventListener("click", () => {
    deck.querySelectorAll(".bench-chip.sel").forEach((c) => c.classList.remove("sel"));
    chip.classList.add("sel");
    if (exps.length) {
      const sel = benchDefaultSelection(b, allExperiments, allAgents);
      if (sel) selectBenchmark(sel.b, sel.exp, sel.agent, { announce: false });
    }
    else {
      traceMsg(`${b.name}: No experiment data matched (only datasets with “${esc(b.key || b.name)}” in their names are linked)`);
      toast(`${b.name}: No data available`);
    }
  });
  return chip;
}

function benchCards(face) {
  const wrap = el("div", "angle-groups");
  face.groups.forEach((group) => {
    const sec = el("div", "angle-group");
    sec.append(el("div", "angle-label", esc(group.label)));
    const cards = el("div", "angle-cards");
    group.items.forEach((item) => {
      const card = el("button", `angle-card d-${item.diff}`);
      card.append(el("span", "angle-year", esc(item.year)));
      card.append(el("strong", null, esc(item.name)));
      card.append(el("span", "angle-note", esc(item.note)));
      card.addEventListener("click", () => toast(`${item.name}: staged benchmark data`));
      cards.append(card);
    });
    sec.append(cards);
    wrap.append(sec);
  });
  return wrap;
}

function skillMemoryGrid(face) {
  const years = [...new Set(face.groups.flatMap((g) => g.items.map((i) => i.year)))].sort();
  const wrap = el("div", "skillmem-wrap");
  const grid = el("div", "skillmem-grid");
  grid.append(el("div", ""));
  face.groups.forEach((g) => grid.append(el("div", "bench-cat", esc(g.label))));
  years.forEach((year) => {
    grid.append(el("div", "bench-year", esc(year)));
    face.groups.forEach((group) => {
      const cell = el("div", "bench-cell");
      group.items.filter((item) => item.year === year).forEach((item) => {
        const card = el("button", `bench-chip d-${item.diff}`);
        card.append(el("strong", null, esc(item.name)));
        card.append(el("span", "fake-note", esc(item.note)));
        card.addEventListener("click", () => toast(`${item.name}: staged benchmark data`));
        cell.append(card);
      });
      grid.append(cell);
    });
  });
  wrap.append(grid);
  return wrap;
}

async function selectBenchmark(b, exp, agent = null, options = {}) {
  const { navigate = true, announce = true } = options;
  if (announce) toast(`Loading ${b.name}${agent ? ` · ${agent.label}` : ""} …`);
  try {
    const [res, context] = await Promise.all([
      fetch(`/api/experiment/${exp.id}`),
      loadExperimentContext(exp.id),
    ]);
    const data = await res.json();
    if (!res.ok) throw new Error(data.error || res.statusText);
    const records = data.records || [];
    if (!records.length) {
      traceMsg(`${b.name}: The experiment exists but has no samples`);
      return toast(`${b.name}: No samples`);
    }

    currentBenchmark = b;
    currentAgent = agent;
    currentExperiment = { ...exp, context, agent };
    currentRecords = records;
    activeSample = 0;

    fillTrace(b, records);
    updateTraceControls(b, agent);
    fillEval(b, records, context);
    buildDots(records.length);
    updateCounter();
    if (navigate) setPanel(1, true); // slide into Trace
  } catch (e) {
    traceMsg(`Failed to load ${b.name}: ${e.message}`);
    if (announce) toast(`Failed to load: ${e.message}`);
  }
}

async function loadExperimentContext(expId) {
  try {
    const res = await fetch(`/api/experiment/${encodeURIComponent(expId)}/context`);
    const data = await res.json();
    if (!res.ok) return null;
    return data.context || null;
  } catch {
    return null;
  }
}

/* show a message inside the Trace panel (replaces the empty placeholder) */
function traceMsg(msg) {
  const controls = $("#trace-controls");
  if (controls) controls.hidden = true;
  $("#trace-vpager").hidden = true;
  const empty = $("#trace-empty");
  empty.hidden = false;
  empty.innerHTML = `<p class="muted">${esc(msg)}</p>`;
  setPanel(1, true);
}

/* ─────────────────────────── Trace: one sample at a time ─────────────────────────── */
function tracePanel() {
  const panel = el("article", "panel trace wide");
  document.getElementById("trace-controls")?.remove(); // drop stale docked controls on rebuild
  const controls = el("div", "trace-controls");
  controls.id = "trace-controls";
  controls.hidden = true;
  const empty = el(
    "div",
    "pane-empty",
    '<p class="muted">← Select a benchmark in Task<br/>(● indicates available data)</p>',
  );
  empty.id = "trace-empty";
  const vp = el("div", "vpager");
  vp.id = "trace-vpager";
  vp.hidden = true;
  panel.append(empty, vp);
  // controls live docked top-left in the global topbar, beside the logo
  const inner = document.querySelector(".topbar-inner");
  inner.insertBefore(controls, inner.firstChild);
  return panel;
}

function fillTrace(b, records) {
  $("#trace-empty").hidden = true;
  const vp = $("#trace-vpager");
  vp.hidden = false;
  vp.innerHTML = "";

  // all samples stacked, wrapped by one pair of braces
  const link = el("div", "tlink");
  const lb = braceBig("left", "Task", b.name, () => setPanel(0, true));
  const stack = el("div", "sstack");
  records.forEach((rec, i) => stack.append(sampleCard(rec, i, records.length)));
  // overall average for the right brace label
  const all = records
    .flatMap((r) => (r.annotations || []).map((a) => a.score))
    .filter((x) => typeof x === "number");
  const avg = all.length ? (all.reduce((s, x) => s + x, 0) / all.length).toFixed(2) : "—";
  const rb = braceBig("right", "Eval", `avg ${avg}`, () => setPanel(2, true));

  link.append(lb, stack, rb);
  vp.append(link);
  bindTraceBraceHeight(stack);
  requestAnimationFrame(syncTraceBraces);
  vp.scrollTo({ top: 0 });
}

function updateTraceControls(b, agent) {
  const controls = $("#trace-controls");
  if (!controls) return;
  controls.hidden = false;

  const exps = benchExperiments(b, allExperiments);
  const enabledAgents = allAgents
    .map((a) => ({ agent: a, exp: findAgentExperiment(exps, a) }))
    .filter((item) => item.exp);
  const agentLabels = enabledAgents.map((item) => item.agent.label);
  const agentIndex = Math.max(0, enabledAgents.findIndex((item) => item.agent.id === agent?.id));
  const modelIndex = Math.max(0, MODEL_OPTIONS.indexOf(currentModel));
  const wheelItems = (items, idx) => {
    const values = items.length ? items : ["—"];
    const n = values.length;
    const row = (offset, cls) =>
      `<div class="trace-wheel-item ${cls}">${esc(values[(idx + offset + n) % n])}</div>`;
    return n === 1
      ? `<div class="trace-wheel-item spacer"></div>${row(0, "active")}<div class="trace-wheel-item spacer"></div>`
      : `${row(-1, "prev")}${row(0, "active")}${row(1, "next")}`;
  };

  controls.innerHTML = `
    <div class="trace-selector-row">
      <div class="trace-select-field trace-bench">
        <span>Benchmark</span>
        <strong>${esc(b.name)}</strong>
      </div>
      <div class="trace-select-field trace-wheel trace-select-agent" tabindex="0" aria-label="Scroll to select agent">
        <span>Agent</span>
        <div class="trace-wheel-window">
          <div class="trace-wheel-track">${wheelItems(agentLabels, agentIndex)}</div>
        </div>
      </div>
      <div class="trace-select-field trace-wheel trace-select-model" tabindex="0" aria-label="Scroll to select model">
        <span>Model</span>
        <div class="trace-wheel-window">
          <div class="trace-wheel-track">${wheelItems(MODEL_OPTIONS, modelIndex)}</div>
        </div>
      </div>
    </div>
  `;

  let wheelLocked = false;
  const cycleByWheel = (e, field, onStep) => {
    const delta = Math.abs(e.deltaY) >= Math.abs(e.deltaX) ? e.deltaY : e.deltaX;
    if (!delta) return;
    e.preventDefault();
    if (wheelLocked) return;
    wheelLocked = true;
    field.classList.add("scrolling");
    onStep(delta > 0 ? 1 : -1);
    setTimeout(() => {
      wheelLocked = false;
      field.classList.remove("scrolling");
    }, 140);
  };

  $(".trace-select-agent", controls)?.addEventListener(
    "wheel",
    (e) => {
      cycleByWheel(e, e.currentTarget, (dir) => {
        if (!enabledAgents.length) return;
        const idx = Math.max(0, enabledAgents.findIndex((item) => item.agent.id === currentAgent?.id));
        const next = enabledAgents[(idx + dir + enabledAgents.length) % enabledAgents.length];
        selectBenchmark(b, next.exp, next.agent, { navigate: false, announce: false });
      });
    },
    { passive: false },
  );

  $(".trace-select-model", controls)?.addEventListener(
    "wheel",
    (e) => {
      cycleByWheel(e, e.currentTarget, (dir) => {
        const idx = Math.max(0, MODEL_OPTIONS.indexOf(currentModel));
        currentModel = MODEL_OPTIONS[(idx + dir + MODEL_OPTIONS.length) % MODEL_OPTIONS.length];
        $(".trace-select-model .trace-wheel-track", controls).innerHTML = wheelItems(MODEL_OPTIONS, MODEL_OPTIONS.indexOf(currentModel));
        fillEval(currentBenchmark || b, currentRecords, currentExperiment?.context);
      });
    },
    { passive: false },
  );

  controls.querySelectorAll(".trace-wheel").forEach((field) => {
    field.addEventListener("keydown", (e) => {
      if (e.key !== "ArrowDown" && e.key !== "ArrowUp") return;
      e.preventDefault();
      const dir = e.key === "ArrowDown" ? 1 : -1;
      field.dispatchEvent(new WheelEvent("wheel", { deltaY: dir, bubbles: true, cancelable: true }));
    });
  });
}

/* one collapsible sample (collapsed by default) */
function sampleCard(rec, i, n) {
  const out = rec.output || {};
  const input = rec.input || {};
  const cardEl = el("div", "scard-card");

  const head = el("div", "sc-head");
  head.append(el("span", "sc-twist", "▸"));
  const ht = el("div", "sc-head-text");
  ht.append(el("div", "sc-title", `Sample ${i + 1} / ${n}`));
  ht.append(
    el("div", "sc-sub", esc(input.instruction || input.question || pretty(input))),
  );
  head.append(ht);
  head.append(statusPill(out.status || (rec.error ? "error" : "ok")));
  cardEl.append(head);

  const body = el("div", "sc-body");
  body.hidden = true;
  body.append(sampleOverview(rec, out, i));
  const brief = el("div", "sample-brief");
  brief.append(sampleBrief("Task", input.instruction || input.question || pretty(input)));
  brief.append(sampleBrief("Agent Answer", out.final_answer || "—"));
  brief.append(sampleExpected(rec.reference_output || {}, out));
  body.append(brief);

  const treeCard = el("div", "card trace-card");
  treeCard.append(sectionTitle("Trace"));
  const tb = el("div");
  tb.append(el("p", "muted", "Loading trace…"));
  treeCard.append(tb);
  body.append(treeCard);
  cardEl.append(body);

  let loaded = false;
  head.addEventListener("click", () => {
    const open = body.hidden; // about to open?
    // accordion: collapse every other sample first
    cardEl.parentElement?.querySelectorAll(".scard-card").forEach((c) => {
      if (c === cardEl) return;
      c.classList.remove("open");
      const b = c.querySelector(".sc-body");
      if (b) b.hidden = true;
    });
    body.hidden = !open;
    cardEl.classList.toggle("open", open);
    requestAnimationFrame(syncTraceBraces);
    if (open) {
      if (!loaded) {
        loadTrace(rec, out, tb);
        loaded = true;
      }
      // keep the opened card in view
      requestAnimationFrame(() => {
        const vp = $("#trace-vpager");
        if (vp) vp.scrollTo({ top: cardEl.offsetTop - 12, behavior: "smooth" });
      });
    }
  });
  return cardEl;
}

function sampleOverview(rec, out, i) {
  const c = el("div", "card run-overview");
  const status = out.status || (rec.error ? "error" : "ok");
  const title = el("div", "run-title");
  title.append(el("div", "run-title-main", "Metric"));
  title.append(statusPill(status));
  c.append(title);

  const stats = el("div", "run-stats");
  stats.append(runStat(rec.latency_ms != null ? fmtMs(rec.latency_ms) : "—", "Latency"));
  stats.append(runStat(out.turns ?? "—", "Turns"));
  stats.append(runStat((out.tool_calls || []).length, "Tool Calls"));
  const score = sampleScore(rec);
  stats.append(runStat(score != null ? score.toFixed(2) : "—", "Avg Score"));
  c.append(stats);

  const evals = (rec.annotations || []).filter((a) => typeof a.score === "number");
  if (evals.length) {
    const row = el("div", "run-evals");
    evals.forEach((a) => {
      const item = el("div", "eval-score");
      item.append(el("span", "eval-score-name", esc(a.name)));
      item.append(el("span", "eval-score-value", a.score.toFixed(2)));
      row.append(item);
    });
    c.append(row);
  }
  return c;
}

function runStat(value, label) {
  const item = el("div", "run-stat");
  item.append(el("div", "run-stat-k", esc(label)));
  item.append(el("div", "run-stat-v", esc(value)));
  return item;
}

function sampleScore(rec) {
  const xs = (rec.annotations || [])
    .map((a) => a.score)
    .filter((x) => typeof x === "number");
  return xs.length ? xs.reduce((s, x) => s + x, 0) / xs.length : null;
}

function sampleBrief(label, text) {
  const c = el("div", "card sample-brief-card");
  c.append(el("p", "card-label", esc(label)));
  c.append(el("p", "sample-copy", esc(text)));
  return c;
}

function sampleExpected(ref, out = {}) {
  const c = el("div", "card sample-brief-card expected-card");
  c.append(sectionTitle("Expected"));
  const hasOutputs = Array.isArray(ref.expected_outputs) && ref.expected_outputs.length;
  const hasActions = Array.isArray(ref.expected_actions) && ref.expected_actions.length;
  const answer = String(out.final_answer || "").toLowerCase();
  const actualTools = (out.tool_calls || []).map((t) =>
    String(typeof t === "string" ? t : t?.name || "").toLowerCase(),
  );
  if (hasOutputs) {
    c.append(el("div", "expected-label", "Answer checks"));
    const checks = el("div", "expected-checks");
    ref.expected_outputs.forEach((o) => {
      const ok = answer.includes(String(o).toLowerCase());
      checks.append(expectedCheckRow({
        ok,
        expected: o,
        observed: ok ? answerSnippet(out.final_answer, o) : "not found in answer",
      }));
    });
    c.append(checks);
  }
  if (hasActions) {
    c.append(el("div", "expected-label", "Action checks"));
    const actions = el("div", "expected-checks");
    ref.expected_actions.forEach((a) => {
      const ok = actualTools.includes(String(a.name || "").toLowerCase());
      actions.append(expectedCheckRow({
        ok,
        expected: a.name || "?",
        detail: a.arguments ? pretty(a.arguments) : "",
        observed: ok ? `called ${a.name}` : "not observed in tool calls",
      }));
    });
    c.append(actions);
  }
  if (!hasOutputs && !hasActions) c.append(el("pre", "json", esc(pretty(ref))));
  return c;
}

function sectionTitle(title) {
  const head = el("div", "run-title section-title");
  head.append(el("div", "run-title-main", esc(title)));
  return head;
}

function expectedCheckRow({ ok, expected, observed, detail = "" }) {
  const row = el("div", `expected-check ${ok ? "pass" : "miss"}`);
  row.append(el("span", `expected-step ${ok ? "pass" : "miss"}`, ok ? "✓" : "×"));
  const main = el("div", "expected-main");
  main.append(el("div", "expected-pair", `<span>Expected</span><strong>${esc(expected)}</strong>`));
  if (detail) main.append(el("pre", "expected-args", esc(detail)));
  main.append(el("div", "expected-pair observed", `<span>Observed</span><strong>${esc(observed)}</strong>`));
  row.append(main);
  return row;
}

function answerSnippet(answer, needle) {
  const text = String(answer || "");
  const q = String(needle || "");
  const idx = text.toLowerCase().indexOf(q.toLowerCase());
  if (idx < 0) return "";
  const start = Math.max(0, idx - 36);
  const end = Math.min(text.length, idx + q.length + 36);
  return `${start ? "..." : ""}${text.slice(start, end)}${end < text.length ? "..." : ""}`;
}

/* a big curly brace that stretches to the height of the sample stack */
function braceBig(side, l1, l2, onClick) {
  const wrap = el("div", `sbrace ${side}`);
  const NS = "http://www.w3.org/2000/svg";
  const svg = document.createElementNS(NS, "svg");
  svg.setAttribute("viewBox", "0 0 30 100");
  svg.setAttribute("preserveAspectRatio", "none");
  const path = document.createElementNS(NS, "path");
  path.setAttribute(
    "d",
    side === "left"
      ? "M27 1 C16 1 21 9 19 24 C17 40 15 46 4 50 C15 54 17 60 19 76 C21 91 16 99 27 99"
      : "M3 1 C14 1 9 9 11 24 C13 40 15 46 26 50 C15 54 13 60 11 76 C9 91 14 99 3 99",
  );
  path.setAttribute("fill", "none");
  path.setAttribute("stroke", "currentColor");
  path.setAttribute("stroke-width", "2");
  path.setAttribute("stroke-linecap", "round");
  path.setAttribute("vector-effect", "non-scaling-stroke");
  svg.appendChild(path);

  const label = el("div", "brace-label");
  label.append(el("div", "brace-l1", esc(l1)));
  label.append(el("div", "brace-l2", esc(l2)));

  if (side === "left") wrap.append(label, svg);
  else wrap.append(svg, label);
  wrap.addEventListener("click", onClick);
  return wrap;
}

function bindTraceBraceHeight(stack) {
  traceBraceObserver?.disconnect();
  if (!stack) return;
  if (typeof ResizeObserver === "function") {
    traceBraceObserver = new ResizeObserver(syncTraceBraces);
    traceBraceObserver.observe(stack);
  }
}

function syncTraceBraces() {
  const link = $("#trace-vpager .tlink");
  const stack = link?.querySelector(".sstack");
  if (!link || !stack) return;
  const h = Math.max(64, Math.ceil(stack.getBoundingClientRect().height));
  link.querySelectorAll(".sbrace").forEach((brace) => {
    brace.style.height = `${h}px`;
  });
}

function sampleMetrics(rec, out) {
  const c = el("div", "card");
  c.append(el("p", "card-label", "Metrics for this sample"));
  const status = out.status || (rec.error ? "error" : "ok");
  const head = el("div");
  head.style.cssText = "display:flex;gap:8px;flex-wrap:wrap;margin-bottom:12px";
  head.append(statusPill(status));
  (rec.annotations || []).forEach((a) => {
    if (typeof a.score === "number")
      head.append(el("span", "pill", `${esc(a.name)} ${a.score.toFixed(2)}`));
  });
  c.append(head);

  const grid = el("div", "metric-grid");
  grid.append(metric(out.turns ?? "—", "turns"));
  grid.append(metric(rec.latency_ms != null ? fmtMs(rec.latency_ms) : "—", "latency"));
  grid.append(
    metric(
      rec.prompt_token_count != null
        ? `${rec.prompt_token_count}+${rec.completion_token_count ?? 0}`
        : "—",
      "tokens",
    ),
  );
  grid.append(metric((out.tool_calls || []).length, "tool calls"));
  c.append(grid);
  return c;
}
function metric(v, k) {
  const m = el("div", "metric");
  m.append(el("div", "metric-v", esc(v)));
  m.append(el("div", "metric-k", esc(k)));
  return m;
}

function expectedCard(ref) {
  const c = el("div", "card");
  c.append(el("p", "card-label", "Expected output"));
  if (Array.isArray(ref.expected_outputs) && ref.expected_outputs.length) {
    const chips = el("div", "chips");
    ref.expected_outputs.forEach((o) => chips.append(el("span", "pill", esc(o))));
    c.append(chips);
  }
  if (Array.isArray(ref.expected_actions) && ref.expected_actions.length) {
    const tl = el("div", "timeline");
    tl.style.marginTop = "12px";
    ref.expected_actions.forEach((a) => {
      const item = el("div", "tl-item");
      item.append(el("div", "tl-name", esc(a.name || "?")));
      if (a.arguments) item.append(el("div", "tl-sub", esc(pretty(a.arguments))));
      tl.append(item);
    });
    c.append(tl);
  }
  if (!ref.expected_outputs && !ref.expected_actions)
    c.append(el("pre", "json", esc(pretty(ref))));
  return c;
}

/* ─────────────────────────── Eval: averages across samples ─────────────────────────── */
function evalPanel() {
  const panel = el("article", "panel eval");
  const body = el("div", "panel-inner");
  body.id = "eval-body";
  body.append(el("p", "kicker", "Eval"));
  body.append(el("p", "muted", "← Select a benchmark in Task"));
  panel.append(body);
  return panel;
}

function fillEval(b, records, context) {
  const body = $("#eval-body");
  body.innerHTML = "";
  body.append(el("p", "kicker", `Eval · ${b.name} all-sample average`));

  // collect evaluator names
  const names = [];
  records.forEach((r) =>
    (r.annotations || []).forEach((a) => {
      if (!names.includes(a.name)) names.push(a.name);
    }),
  );
  const avgOf = (name) => {
    const xs = records
      .map((r) => (r.annotations || []).find((a) => a.name === name)?.score)
      .filter((x) => typeof x === "number");
    return xs.length ? xs.reduce((s, x) => s + x, 0) / xs.length : null;
  };

  // summary
  const allAvgs = names.map(avgOf).filter((x) => x != null);
  const overall = allAvgs.length
    ? allAvgs.reduce((s, x) => s + x, 0) / allAvgs.length
    : null;
  const passes = records.filter((r) =>
    (r.annotations || []).some((a) => a.name === "llm_judge" && a.score >= 0.5),
  ).length;
  const avgLatency = avgNumber(records.map((r) => r.latency_ms));
  const summary = evalSummaryCard({ overall, records, passes, avgLatency, evaluatorCount: names.length });
  summary.append(evalContextCard(b, records, context, true));
  body.append(summary);
  body.append(evalFishboneCard(records, overall));
  body.append(evalAssessmentCard(records));
}

function evalSummaryCard({ overall, records, passes, avgLatency, evaluatorCount }) {
  const c = el("div", "card eval-summary-card");
  c.append(el("p", "card-label", "SUMMARY"));
  const hasScore = typeof overall === "number";
  const pct = hasScore ? Math.max(0, Math.min(100, overall * 100)) : 0;
  const good = hasScore && overall >= 0.5;
  const main = el("div", "eval-summary-main");
  const ring = el(
    "div",
    `ring summary-ring ${hasScore ? (good ? "good" : "bad") : ""}`,
    hasScore ? overall.toFixed(2) : "—",
  );
  ring.style.setProperty("--p", pct);
  const copy = el("div", "summary-copy");
  copy.append(el("div", "summary-title", "Overall evaluator score"));
  copy.append(
    el(
      "div",
      "summary-sub",
      `${records.length} samples · ${evaluatorCount || 0} evaluators`,
    ),
  );
  main.append(ring, copy);
  c.append(main);

  const stats = el("div", "summary-stat-grid");
  stats.append(metric(records.length, "samples"));
  stats.append(metric(`${passes}/${records.length}`, "llm pass"));
  stats.append(metric(avgLatency != null ? fmtMs(avgLatency) : "—", "avg latency"));
  c.append(stats);
  return c;
}

function evalContextCard(b, records, context, embedded = false) {
  const c = embedded ? el("details", "summary-config") : el("div", "card eval-info-card compact");
  const target = embedded ? el("div", "eval-info-card compact embedded") : c;
  if (embedded) c.append(el("summary", null, "Configuration"));
  else c.append(el("p", "card-label", "Configuration"));
  if (context && context.available === false) {
    if (embedded) c.append(target);
    return c;
  }

  const exp = context?.experiment || currentExperiment || {};
  const dataset = context?.dataset || {};
  const inputs = context?.inputs || {};
  const modelNames = modelLabels(context);
  const modelOverride = currentModel;
  const domain = CATS[b.cat] || joinList(inputs.domains) || benchFamily(b) || inferDomain(dataset.name || b.name);
  const agentLabel =
    currentExperiment?.agent?.label ||
    joinList(context?.agent?.frameworks) ||
    joinList(context?.agent?.names) ||
    "—";
  const runStats = context?.runs || {};
  const okRuns =
    runStats.ok_runs != null && runStats.runs != null
      ? `${runStats.ok_runs}/${runStats.runs}`
      : records.length
        ? `${records.filter(isOkRun).length}/${records.length}`
        : "—";

  const grid = el("div", "info-grid");
  grid.append(infoItem("Agent", agentLabel));
  grid.append(infoItem("Model", modelOverride || joinList(modelNames)));
  grid.append(infoItem("Benchmark", b.name));
  grid.append(infoItem("Dataset", dataset.name || currentExperiment?.dataset_name));
  grid.append(infoItem("Project ID", exp.project_name || currentExperiment?.project_name));
  grid.append(infoItem("Domain", domain));
  grid.append(infoItem("Test Time", timeRange(runStats.first_start_time, runStats.last_end_time) || fmtDateTime(exp.created_at)));
  grid.append(infoItem("Runs OK", okRuns));
  target.append(grid);

  const chipSections = [
    ["Expected Actions", inputs.expected_actions || []],
    ["Expected Outputs", inputs.expected_outputs || []],
  ].filter(([, xs]) => xs && xs.length);
  if (chipSections.length) {
    const chips = el("div", "eval-chip-sections");
    chipSections.forEach(([label, xs]) => {
      const sec = el("div", "eval-chip-section");
      sec.append(el("div", "eval-chip-label", esc(label)));
      const row = el("div", "chips compact");
      xs.slice(0, 12).forEach((x) => row.append(el("span", "pill", esc(x))));
      if (xs.length > 12) row.append(el("span", "pill", `+${xs.length - 12}`));
      sec.append(row);
      chips.append(sec);
    });
    target.append(chips);
  }

  if (embedded) c.append(target);
  return c;
}

function evalFishboneCard(records, overall) {
  const c = el("div", "card eval-fishbone-card");
  c.append(el("p", "card-label", "DIAGNOSIS"));
  const fish = el("div", "fishbone");
  fish.append(el("div", "fish-end fish-head", "HEAD"));
  fish.append(el("div", "fish-end fish-tail", "TAIL"));
  const planSubMetrics = [
    ["plan_grade", annotationAverage(records, "plan_grade")],
    ["plan_goal_alignment", annotationAverage(records, "plan_goal_alignment")],
    ["plan_completeness", annotationAverage(records, "plan_completeness")],
    ["plan_constraint_adherence", annotationAverage(records, "plan_constraint_adherence")],
    ["reasoning_coherence", annotationAverage(records, "reasoning_coherence")],
    ["plan_hallucination", annotationAverage(records, "plan_hallucination")],
  ];
  const toolSubMetrics = [
    ["tool_hallucination", annotationAverage(records, "tool_hallucination")],
    ["tool_invocation", annotationAverage(records, "tool_invocation")],
    ["self_correction_rate", annotationAverage(records, "self_correction_rate")],
    ["tool_call_count", annotationAverage(records, "tool_call_count")],
  ];
  const svgNS = "http://www.w3.org/2000/svg";
  const expandables = [];
  [
    ["Plan", "plan_parsimony", annotationAverage(records, "plan_parsimony"), planSubMetrics],
    ["Memory", "hallucination", annotationAverage(records, "hallucination")],
    ["Skill", "conciseness", annotationAverage(records, "conciseness")],
    ["Tool", "tool_recall", annotationAverage(records, "tool_recall"), toolSubMetrics],
    ["Final_Result", "overall_score", overall],
  ].forEach(([node, metricName, score, subMetrics], i) => {
    const item = el("div", `fish-item ${i % 2 ? "lower" : "upper"}`);
    item.append(
      el(
        "div",
        "fish-branch",
        `<span>${esc(metricName)}</span><strong>${esc(formatScore(score))}</strong>`,
      ),
    );
    const fishNode = el(
      "div",
      "fish-node",
      `<span>${String(i + 1).padStart(2, "0")}</span>${esc(node)}`,
    );
    if (subMetrics && subMetrics.length) {
      item.classList.add("fish-item-expandable");
      fishNode.append(el("i", "fish-expand-caret", "▸"));
      fishNode.setAttribute("role", "button");
      fishNode.setAttribute("tabindex", "0");
      fishNode.setAttribute("aria-expanded", "false");
      const entry = { item, fishNode, subPanel: buildSubFishbone(node, subMetrics), open: false };
      fishNode.addEventListener("click", () => toggle(entry));
      fishNode.addEventListener("keydown", (e) => {
        if (e.key === "Enter" || e.key === " ") {
          e.preventDefault();
          toggle(entry);
        }
      });
      expandables.push(entry);
    }
    item.append(fishNode);
    fish.append(item);
  });
  c.append(fish);

  expandables.forEach((e) => {
    const svg = document.createElementNS(svgNS, "svg");
    svg.setAttribute("class", "sub-connector");
    e.path = document.createElementNS(svgNS, "path");
    e.path.setAttribute("class", "sub-connector-path");
    svg.append(e.path);
    e.svg = svg;
    c.append(svg);
    c.append(e.subPanel);
    e.subPanel.addEventListener("transitionend", (ev) => {
      if (ev.propertyName === "grid-template-rows") redrawAll();
    });
  });

  function drawConnector(e) {
    const cap = e.subPanel.querySelector(".sub-spine-cap");
    if (!cap) return;
    const cr = c.getBoundingClientRect();
    const ir = e.item.getBoundingClientRect();
    const nr = e.fishNode.getBoundingClientRect();
    const pr = cap.getBoundingClientRect();
    // start from the node center; for "upper" nodes leave from the node bottom,
    // for "lower" nodes leave from below the item so the line clears the branch box.
    const isLower = e.item.classList.contains("lower");
    const nx = nr.left + nr.width / 2 - cr.left;
    const ny = (isLower ? ir.bottom : nr.bottom) - cr.top;
    const sx = pr.left + pr.width / 2 - cr.left;
    const sy = pr.top + pr.height / 2 - cr.top;
    e.svg.setAttribute("width", cr.width);
    e.svg.setAttribute("height", c.scrollHeight);
    const dir = sx < nx ? -1 : 1;
    const r = Math.max(0, Math.min(12, Math.abs(sx - nx) / 2, Math.abs(sy - ny) / 2));
    e.path.setAttribute(
      "d",
      `M ${nx} ${ny} L ${nx} ${sy - r} Q ${nx} ${sy} ${nx + dir * r} ${sy} L ${sx} ${sy}`,
    );
  }
  function redrawAll() {
    expandables.forEach((e) => {
      if (e.open) drawConnector(e);
    });
  }
  function setOpen(e, open) {
    e.open = open;
    e.subPanel.classList.toggle("open", open);
    e.item.classList.toggle("open", open);
    e.svg.classList.toggle("open", open);
    e.fishNode.setAttribute("aria-expanded", open ? "true" : "false");
  }
  function toggle(e) {
    const next = !e.open;
    // accordion: opening one collapses the others
    expandables.forEach((other) => {
      if (other !== e && other.open) setOpen(other, false);
    });
    setOpen(e, next);
    requestAnimationFrame(() => requestAnimationFrame(redrawAll));
  }
  if (expandables.length) window.addEventListener("resize", redrawAll);
  return c;
}

function buildSubFishbone(parentNode, subMetrics) {
  const wrap = el("div", "sub-fishbone-wrap");
  const inner = el("div", "sub-fishbone-inner");
  const sub = el("div", "fishbone fishbone-vertical sub-fishbone");
  // cap sits at the top of the vertical sub-spine; the connector from the
  // parent node lands exactly on it, so the two charts read as one tree.
  sub.append(el("div", "sub-spine-cap", esc(parentNode)));
  subMetrics.forEach(([name, score], i) => {
    const item = el("div", "fish-item");
    item.append(
      el("div", "fish-node", `<span>${String(i + 1).padStart(2, "0")}</span>${esc(name)}`),
    );
    item.append(
      el(
        "div",
        "fish-branch",
        `<span>avg</span><strong>${esc(formatMetricValue(name, score))}</strong>`,
      ),
    );
    sub.append(item);
  });
  inner.append(sub);
  wrap.append(inner);
  return wrap;
}

function evalAssessmentCard(records) {
  const c = el("div", "card eval-assessment-card");
  c.append(el("p", "card-label", "EVALUATION"));
  const tree = el("div", "assessment-tree");
  tree.append(el("div", "assessment-root", "<span>Eval Tree</span><strong>Metrics</strong>"));
  // Safety metrics come straight from eval/metrics_catalog.json (safety group);
  // fall back to just hallucination if the catalog could not be loaded.
  const safetyNames = catalogGroupMetrics("safety");
  const safetyMetrics = (safetyNames.length ? safetyNames : ["hallucination"]).map((name) => [
    name,
    annotationAverage(records, name),
  ]);
  [
    ["Efficiency", [["total_token_usage", totalTokenUsage(records)], ["cost", annotationAverage(records, "cost")]]],
    ["Safety", safetyMetrics],
    ["Accuracy", [["correctness", annotationAverage(records, "correctness")]]],
  ].forEach(([label, metrics], i) => {
    const row = el("div", "assessment-row");
    row.append(el("div", "assessment-label", `<span>${String(i + 1).padStart(2, "0")}</span><strong>${esc(label)}</strong>`));
    const values = el("div", "assessment-values");
    metrics.forEach(([name, value]) => {
      values.append(
        el(
          "div",
          "assessment-metric",
          `<span>${esc(name)}</span><strong>${esc(formatMetricValue(name, value))}</strong>`,
        ),
      );
    });
    row.append(values);
    tree.append(row);
  });
  c.append(tree);
  return c;
}

function annotationAverage(records, name) {
  const target = String(name).toLowerCase();
  const xs = records
    .map((r) => (r.annotations || []).find((a) => String(a.name).toLowerCase() === target)?.score)
    .filter((x) => typeof x === "number");
  return xs.length ? xs.reduce((s, x) => s + x, 0) / xs.length : null;
}

function totalTokenUsage(records) {
  let total = 0;
  let seen = false;
  records.forEach((r) => {
    const prompt = typeof r.prompt_token_count === "number" ? r.prompt_token_count : 0;
    const completion = typeof r.completion_token_count === "number" ? r.completion_token_count : 0;
    if (prompt || completion) seen = true;
    total += prompt + completion;
  });
  return seen ? total : annotationAverage(records, "total_token_usage");
}

function formatScore(value) {
  return typeof value === "number" ? value.toFixed(2) : "—";
}

function formatMetricValue(name, value) {
  if (typeof value !== "number") return "—";
  if (name === "total_token_usage") return Math.round(value).toLocaleString("en-US");
  if (name === "tool_call_count") return (Math.round(value * 10) / 10).toLocaleString("en-US");
  return value.toFixed(2);
}

function infoItem(label, value) {
  const item = el("div", "info-item");
  item.append(el("div", "info-label", esc(label)));
  item.append(el("div", "info-value", esc(value == null || value === "" ? "—" : value)));
  return item;
}

function isOkRun(record) {
  const status = String(record?.output?.status || "").toLowerCase();
  return !record?.error && status !== "error" && status !== "failed";
}

const uniq = (xs) => {
  const out = [];
  xs.forEach((x) => {
    if (x == null || x === "") return;
    const v = String(x);
    if (!out.includes(v)) out.push(v);
  });
  return out;
};
const joinList = (xs) => (xs && xs.length ? xs.join(", ") : "");
function modelLabels(context) {
  const taskModels = context?.models?.task || [];
  const task = taskModels.map((m) => [m.provider, m.name].filter(Boolean).join("/"));
  const observed = (context?.models?.observed || []).filter((m) => !task.some((t) => t.endsWith(m)));
  return uniq([...task, ...observed]);
}
const avgNumber = (xs) => {
  const nums = xs.filter((x) => typeof x === "number");
  return nums.length ? nums.reduce((s, x) => s + x, 0) / nums.length : null;
};
function timeRange(start, end) {
  if (!start && !end) return "";
  if (!start || start === end) return fmtDateTime(start || end);
  return `${fmtDateTime(start)} - ${fmtDateTime(end)}`;
}
function fmtDateTime(value) {
  if (!value) return "";
  const normalized = String(value).trim().replace(" ", "T");
  const d = new Date(normalized.endsWith("Z") || /[+-]\d\d:?\d\d$/.test(normalized) ? normalized : `${normalized}Z`);
  if (Number.isNaN(d.getTime())) return String(value);
  const parts = new Intl.DateTimeFormat("zh-CN", {
    timeZone: "UTC",
    year: "numeric",
    month: "2-digit",
    day: "2-digit",
    hour: "numeric",
    minute: "2-digit",
    second: "2-digit",
    hour12: true,
  }).formatToParts(d);
  const get = (type) => parts.find((p) => p.type === type)?.value || "";
  const dayPeriod = get("dayPeriod");
  return `${get("year")}/${get("month")}/${get("day")} ${dayPeriod}${get("hour")}:${get("minute")}:${get("second")}`;
}
function inferDomain(name = "") {
  const m = String(name).match(/(?:^|[-_])(retail|airline|web|coding|research|computer)(?:[-_]|$)/i);
  return m ? m[1] : "";
}

/* ═══════════════════════ span tree (A2E-structured) ═══════════════════════ */
async function loadTrace(rec, out, mount) {
  const project = currentExperiment?.project_name;
  if (!rec.trace_id || !project) {
    fallbackTools(out, mount);
    requestAnimationFrame(syncTraceBraces);
    return;
  }
  try {
    const url = `/api/trace?project=${encodeURIComponent(project)}&trace_id=${encodeURIComponent(rec.trace_id)}`;
    const res = await fetch(url);
    const data = await res.json();
    const spans = data.spans || [];
    if (!spans.length) {
      fallbackTools(out, mount);
      requestAnimationFrame(syncTraceBraces);
      return;
    }
    mount.innerHTML = "";
    mount.append(renderTree(spans));
  } catch {
    fallbackTools(out, mount);
  }
  requestAnimationFrame(syncTraceBraces);
}
function fallbackTools(out, mount) {
  mount.innerHTML = "";
  const tools = out.tool_calls || [];
  if (!tools.length) return mount.append(el("p", "muted", "No trace available"));
  const tl = el("div", "timeline");
  tools.forEach((t, i) => {
    const item = el("div", "tl-item");
    item.append(el("div", "tl-name", esc(typeof t === "string" ? t : t.name || pretty(t))));
    item.append(el("div", "tl-sub", `step ${i + 1}`));
    tl.append(item);
  });
  mount.append(tl);
}

const KIND = {
  LLM: { c: "#7c5cff", g: "LM" },
  PROMPT: { c: "#9b5de5", g: "PR" },
  CHAIN: { c: "#1f7ae0", g: "CH" },
  AGENT: { c: "#e83e8c", g: "AG" },
  TOOL: { c: "#c98f00", g: "TL" },
  RETRIEVER: { c: "#0f9fbc", g: "RT" },
  EMBEDDING: { c: "#7b61ff", g: "EM" },
  RERANKER: { c: "#45a834", g: "RR" },
  EVALUATOR: { c: "#7b61ff", g: "EV" },
  GUARDRAIL: { c: "#e63946", g: "GD" },
  UNKNOWN: { c: "#7c8794", g: "··" },
};
const INDENT = 34;

function renderTree(spans) {
  spans = normalizeVisibleSpans(spans);
  const byId = new Map();
  spans.forEach((s, i) => byId.set(spanId(s, i), { span: s, children: [] }));
  const roots = [];
  spans.forEach((s, i) => {
    const node = byId.get(spanId(s, i));
    const parent = s.parent_id && byId.get(s.parent_id);
    if (parent) parent.children.push(node);
    else roots.push(node);
  });
  const start = (n) => +new Date(n.span.start_time);
  const sortRec = (n) => {
    n.children.sort((a, b) => start(a) - start(b));
    n.children.forEach(sortRec);
  };
  roots.sort((a, b) => start(a) - start(b));
  roots.forEach(sortRec);

  const t0 = Math.min(...spans.map((s) => +new Date(s.start_time)));
  const t1 = Math.max(...spans.map((s) => +new Date(s.end_time)));
  const total = Math.max(1, t1 - t0);

  const wrap = el("div", "trace-flow");
  const head = el("div", "trace-flow-head");
  head.append(el("div", "trace-flow-title", "Agent Run"));
  head.append(el("div", "trace-flow-sub", `total ${fmtMs(total)} · ${kindSummary(spans)}`));
  wrap.append(head);

  const ul = el("ul", "trace-flow-list");
  roots.forEach((n, i) => ul.append(treeLi(n, 0, t0, total, i === roots.length - 1)));
  wrap.append(ul);
  return wrap;
}

function spanId(span, index) {
  return span?.context?.span_id || span?.span_id || `span-${index}`;
}

function treeLi(node, level, t0, total, isLast) {
  const li = el("li");
  li.className = `trace-flow-item ${level ? "child" : "root"} ${isTraceRootNode(node) ? "flow-root" : ""} ${isLast ? "last" : ""}`;
  li.style.setProperty("--level", level);
  if (level > 0) {
    const edge = el("span", "trace-edge");
    edge.style.left = (level - 1) * INDENT + 11 + "px";
    edge.style.width = INDENT + "px";
    li.append(edge);
    if (!isLast) {
      const cont = el("span", "trace-edge-cont");
      cont.style.left = (level - 1) * INDENT + 11 + "px";
      li.append(cont);
    }
  }
  const { row, detail } = nodeRow(node, level, t0, total);
  li.append(row, detail);
  if (node.children.length) {
    const kids = el("ul", "node-kids trace-flow-kids");
    node.children.forEach((c, i) =>
      kids.append(treeLi(c, level + 1, t0, total, i === node.children.length - 1)),
    );
    li.append(kids);
  }
  return li;
}

function isTraceRootNode(node) {
  return /^LangGraph$/i.test(String(node?.span?.name || ""));
}

function isInternalSpan(span) {
  const name = String(span?.name || "");
  const kind = String(span?.span_kind || "").toUpperCase();
  return (
    /^_branch_after_/i.test(name) ||
    /^Task:\s*task_fn$/i.test(name) ||
    (kind === "AGENT" && /^agent\./i.test(name))
  );
}

function normalizeVisibleSpans(spans) {
  const original = new Map();
  spans.forEach((s, i) => original.set(spanId(s, i), s));
  const visible = spans.filter((s) => !isInternalSpan(s));
  const visibleIds = new Set(visible.map((s, i) => spanId(s, i)));
  return visible
    .map((s) => {
      let parent = s.parent_id;
      while (parent && !visibleIds.has(parent)) {
        parent = original.get(parent)?.parent_id || null;
      }
      if (!parent && s.parent_id) {
        parent = nearestVisibleContainer(s, visible);
      }
      return parent === s.parent_id ? s : { ...s, parent_id: parent };
    });
}

function nearestVisibleContainer(span, visible) {
  const s0 = +new Date(span.start_time);
  const s1 = +new Date(span.end_time);
  let best = null;
  let bestDur = Infinity;
  visible.forEach((candidate, i) => {
    const id = spanId(candidate, i);
    if (id === spanId(span, -1)) return;
    const c0 = +new Date(candidate.start_time);
    const c1 = +new Date(candidate.end_time);
    if (c0 <= s0 && c1 >= s1) {
      const dur = c1 - c0;
      if (dur < bestDur) {
        best = id;
        bestDur = dur;
      }
    }
  });
  return best;
}

function nodeRow(node, level, t0, total) {
  const s = node.span;
  const durMs = Math.max(0, +new Date(s.end_time) - +new Date(s.start_time));
  const offPct = ((+new Date(s.start_time) - t0) / total) * 100;
  const widPct = Math.max(1.5, (durMs / total) * 100);
  const kind = (s.span_kind || "UNKNOWN").toUpperCase();
  const k = KIND[kind] || KIND.UNKNOWN;
  const isErr = String(s.status_code).toUpperCase() === "ERROR";
  const hasKids = node.children.length > 0;
  const tokens = tokenTotal(s.attributes);

  const row = el("div", "trace-node");
  row.style.setProperty("--kind-color", k.c);
  row.style.marginLeft = level * INDENT + "px";

  const rail = el("div", "trace-node-rail");
  rail.append(el("span", "trace-node-dot"));
  row.append(rail);

  const body = el("div", "trace-node-body");
  const top = el("div", "trace-node-top");
  top.append(el("span", "trace-kind", esc(kind)));
  top.append(el("span", "trace-node-name", esc(s.name || "span")));
  body.append(top);

  row.append(body);

  const timing = el("div", "trace-node-time");
  const timeMeta = el("div", "trace-time-meta");
  const meta = el("span", "trace-node-meta", fmtMs(durMs));
  if (tokens) meta.textContent += ` · ${tokens} tok`;
  timeMeta.append(meta);
  if (isErr) timeMeta.append(el("span", "trace-status err", "ERROR"));
  else if (String(s.status_code).toUpperCase() === "OK") timeMeta.append(el("span", "trace-status ok", "OK"));
  timing.append(timeMeta);
  const track = el("div", "trace-mini-track");
  const bar = el("div", "bar");
  bar.style.left = offPct + "%";
  bar.style.width = widPct + "%";
  bar.style.background = k.c;
  track.append(bar);
  timing.append(track);
  row.append(timing);

  const twist = el("button", "trace-twist" + (hasKids ? "" : " hidden"), "▾");
  row.append(twist);

  const detail = el("div", "node-detail");
  detail.style.setProperty("--detail-indent", level * INDENT + "px");
  detail.hidden = true;
  let built = false;

  twist.addEventListener("click", (e) => {
    e.stopPropagation();
    const kids = row.parentElement.querySelector(":scope > .node-kids");
    if (kids) kids.classList.toggle("collapsed");
    twist.classList.toggle("collapsed");
  });
  row.addEventListener("click", () => {
    if (!built) {
      detail.append(spanDetail(s));
      built = true;
    }
    const open = detail.hidden;
    detail.hidden = !open;
    row.classList.toggle("sel", open);
  });
  return { row, detail };
}

function spanDetail(s) {
  const a = s.attributes || {};
  const box = el("div");
  const kind = (s.span_kind || "").toLowerCase();
  const inMsgs = collectMessages(a, "llm.input_messages");
  const outMsgs = collectMessages(a, "llm.output_messages");
  if (kind === "llm" && (inMsgs.length || outMsgs.length)) {
    if (inMsgs.length) box.append(section("Input messages", messagesEl(inMsgs)));
    if (outMsgs.length) box.append(section("Output messages", messagesEl(outMsgs)));
  } else {
    const inp = attrValue(a, "input.value") ?? attrValue(a, "input");
    const outp = attrValue(a, "output.value") ?? attrValue(a, "output");
    if (inp != null) box.append(section("Input", valueEl(inp)));
    if (outp != null) box.append(section("Output", valueEl(outp)));
  }
  const d = el("details", "raw");
  d.append(el("summary", null, "All attributes"));
  d.append(el("pre", "json", esc(pretty(a))));
  box.append(section("", d));
  return box;
}
function section(label, node) {
  const sec = el("div", "detail-sec");
  if (label) sec.append(el("p", "card-label", esc(label)));
  sec.append(node);
  return sec;
}
function valueEl(v) {
  return el("pre", "json", esc(trunc(pretty(v))));
}
function messagesEl(msgs) {
  const box = el("div");
  msgs.forEach((m) => {
    const c = el("div", "msg");
    c.append(el("div", "msg-role", esc(m.role || "message")));
    c.append(el("div", "msg-content", esc(trunc(m.content || pretty(m)))));
    box.append(c);
  });
  return box;
}
function collectMessages(attrs, prefix) {
  const nested = attrValue(attrs, prefix);
  if (Array.isArray(nested))
    return nested.map((m) => ({
      role: m?.message?.role ?? m?.role,
      content: m?.message?.content ?? m?.content,
    }));
  if (Array.isArray(attrs[prefix]))
    return attrs[prefix].map((m) => ({
      role: m?.message?.role ?? m?.role,
      content: m?.message?.content ?? m?.content,
    }));
  const out = [];
  Object.keys(attrs).forEach((key) => {
    const m = key.match(new RegExp(`^${prefix}\\.(\\d+)\\.message\\.(role|content)$`));
    if (!m) return;
    (out[+m[1]] ||= {})[m[2]] = attrs[key];
  });
  return out.filter(Boolean);
}
function attrValue(attrs, path) {
  if (attrs[path] != null) return attrs[path];
  const parts = path.split(".");
  let cur = attrs;
  for (const part of parts) {
    if (!cur || typeof cur !== "object") return null;
    cur = cur[part];
  }
  return cur;
}
function kindSummary(spans) {
  const counts = {};
  spans.forEach((s) => {
    const k = String(s.span_kind || "UNKNOWN").toUpperCase();
    counts[k] = (counts[k] || 0) + 1;
  });
  return Object.entries(counts)
    .sort((a, b) => b[1] - a[1])
    .slice(0, 4)
    .map(([k, n]) => `${n} ${k.toLowerCase()}`)
    .join(" · ");
}
function tokenTotal(a = {}) {
  return (
    attrValue(a, "llm.token_count.total") ??
    ((attrValue(a, "llm.token_count.prompt") || 0) + (attrValue(a, "llm.token_count.completion") || 0) ||
      null)
  );
}
const trunc = (s, n = 1600) => (s.length > n ? s.slice(0, n) + " …(truncated)" : s);
const fmtMs = (ms) =>
  typeof ms !== "number"
    ? "—"
    : ms >= 1000
      ? (ms / 1000).toFixed(2) + "s"
      : Math.round(ms) + "ms";

/* ─────────────────────────── small builders ─────────────────────────── */
function card(label, node) {
  const c = el("div", "card");
  if (label) c.append(el("p", "card-label", esc(label)));
  c.append(node);
  return c;
}
function statusPill(status) {
  const s = String(status).toLowerCase();
  const cls = s === "ok" || s === "correct" ? "ok" : s === "error" ? "err" : "warn";
  return el("span", `pill ${cls}`, esc(status));
}
function evalCard(a) {
  const c = el("div", "card eval-card");
  const hasScore = typeof a.score === "number";
  const pct = hasScore ? Math.max(0, Math.min(100, a.score * 100)) : 0;
  const good = hasScore && a.score >= 0.5;
  const ring = el(
    "div",
    `ring ${hasScore ? (good ? "good" : "bad") : ""}`,
    hasScore ? a.score.toFixed(2).replace(/^0/, "") : "—",
  );
  ring.style.setProperty("--p", pct);
  const body = el("div", "eval-body");
  body.append(el("div", "eval-name", esc(a.name || "evaluator")));
  if (a.label) body.append(el("div", "eval-label", esc(a.label)));
  if (a.explanation) body.append(el("div", "eval-expl", esc(a.explanation)));
  c.append(ring, body);
  return c;
}

/* ─────────────────────────── interaction ─────────────────────────── */
function setPanel(idx, scroll = true) {
  idx = Math.max(0, Math.min(2, idx));
  activePanel = idx;
  if (scroll) {
    const panel = deck.children[idx];
    if (panel) {
      const target = panel.offsetLeft - (deck.clientWidth - panel.offsetWidth) / 2;
      deck.scrollTo({ left: target, behavior: "smooth" });
    }
  }
  paintPeek(deck);
  updateSeg();
}
/* fractional 0..2 position of the viewport center across the panels */
function scrollFraction() {
  const cc = deck.scrollLeft + deck.clientWidth / 2;
  const centers = [...deck.children].map((p) => p.offsetLeft + p.offsetWidth / 2);
  if (!centers.length) return 0;
  if (cc <= centers[0]) return 0;
  if (cc >= centers[centers.length - 1]) return centers.length - 1;
  for (let i = 0; i < centers.length - 1; i++) {
    if (cc >= centers[i] && cc <= centers[i + 1])
      return i + (cc - centers[i]) / (centers[i + 1] - centers[i]);
  }
  return 0;
}

/* slide the whole label strip so the (fractional) active label sits centered —
   the labels drift like a background tracking the content scroll */
function updateSeg() {
  const frac = scrollFraction();
  const segs = [...segTrack.children];
  if (!segs.length) return;
  const centers = segs.map((s) => s.offsetLeft + s.offsetWidth / 2);
  const i = Math.floor(frac);
  const f = frac - i;
  const c = i + 1 < centers.length ? centers[i] + (centers[i + 1] - centers[i]) * f : centers[i];
  segTrack.style.setProperty("--shift", `${segmented.clientWidth / 2 - c}px`);

  const idx = Math.round(frac);
  activePanel = idx;
  segs.forEach((b, k) => b.classList.toggle("active", k === idx));
}
window.addEventListener("resize", () => {
  paintPeek(deck);
  updateSeg();
  syncTraceBraces();
});

function nearestPanel(pager) {
  const cc = pager.scrollLeft + pager.clientWidth / 2;
  let best = 0,
    bd = Infinity;
  [...pager.children].forEach((p, i) => {
    const d = Math.abs(p.offsetLeft + p.offsetWidth / 2 - cc);
    if (d < bd) {
      bd = d;
      best = i;
    }
  });
  return best;
}
function paintPeek(pager) {
  const cc = pager.scrollLeft + pager.clientWidth / 2;
  [...pager.children].forEach((p) => {
    const d = Math.min(
      1,
      Math.abs(p.offsetLeft + p.offsetWidth / 2 - cc) / pager.clientWidth,
    );
    p.style.opacity = (1 - 0.45 * d).toFixed(3);
    p.style.transform = `scale(${(1 - 0.06 * d).toFixed(3)})`;
  });
}

segmented.querySelectorAll(".seg").forEach((btn) =>
  btn.addEventListener("click", () => setPanel(+btn.dataset.panel, true)),
);

window.addEventListener("keydown", (e) => {
  if (e.key === "ArrowRight") setPanel(activePanel + 1, true);
  else if (e.key === "ArrowLeft") setPanel(activePanel - 1, true);
  else if (e.key === "ArrowDown" || e.key === "ArrowUp") {
    const vp = $("#trace-vpager");
    if (vp && !vp.hidden) {
      const cards = vp.querySelectorAll(".scard-card");
      const next = Math.max(
        0,
        Math.min(cards.length - 1, activeSample + (e.key === "ArrowDown" ? 1 : -1)),
      );
      if (cards[next]) vp.scrollTo({ top: cards[next].offsetTop - 12, behavior: "smooth" });
    }
  }
});

/* index of the sample card nearest the top of the trace viewport */
function activeCardIndex() {
  const vp = $("#trace-vpager");
  const cards = [...vp.querySelectorAll(".scard-card")];
  if (!cards.length) return -1;
  const ref = vp.getBoundingClientRect().top + 100;
  let best = 0,
    bd = Infinity;
  cards.forEach((c, i) => {
    const d = Math.abs(c.getBoundingClientRect().top - ref);
    if (d < bd) {
      bd = d;
      best = i;
    }
  });
  return best;
}

/* sample dots (reflect Trace samples) */
function buildDots(n) {
  dotsEl.innerHTML = "";
  for (let i = 0; i < n; i++) {
    const dot = el("span", "dot" + (i === 0 ? " active" : ""));
    dot.addEventListener("click", () => {
      setPanel(1, true);
      const vp = $("#trace-vpager");
      const card = vp.querySelectorAll(".scard-card")[i];
      if (card) vp.scrollTo({ top: card.offsetTop - 12, behavior: "smooth" });
    });
    dotsEl.append(dot);
  }
}
function paintDots() {
  dotsEl.querySelectorAll(".dot").forEach((d, i) =>
    d.classList.toggle("active", i === activeSample),
  );
}
function updateCounter() {
  if (counterEl) counterEl.dataset.sample = currentRecords.length ? `${activeSample + 1}/${currentRecords.length}` : "";
}

/* ─────────────────────────── toast + overlay ─────────────────────────── */
let toastTimer;
function toast(msg) {
  toastEl.textContent = msg;
  toastEl.classList.add("show");
  clearTimeout(toastTimer);
  toastTimer = setTimeout(() => toastEl.classList.remove("show"), 1800);
}
function showOverlay(msg, loading) {
  overlay.classList.remove("hidden");
  overlayMsg.textContent = msg;
  spinner.classList.toggle("hidden", !loading);
  retry.hidden = !!loading;
}
function showError(msg) {
  showOverlay(msg, false);
}
function hideOverlay() {
  overlay.classList.add("hidden");
}
retry.addEventListener("click", load);

load();
