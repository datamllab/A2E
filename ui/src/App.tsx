import { useCallback, useEffect, useState } from "react";
import { listExperiments } from "./api/experiments";
import type { ExperimentSummary } from "./api/types";
import { Deck } from "./components/Deck";
import capabilityFlower from "./assets/capability-flower.jpeg";
import openCompassLogo from "./assets/opencompass.png";

type AppView = "home" | "workspace" | "capability-boundary";

const CAPABILITY_HARNESSES = [
  ["LangGraph"],
  ["CrewAI"],
  ["Google", "ADK"],
  ["AutoGen"],
  ["Smolagents"],
  ["Agno"],
  ["LlamaIndex"],
  ["Claude", "SDK"],
  ["OpenAI", "Agents"],
] as const;

interface CapabilityResult {
  benchmark: string;
  benchmarkMarkup?: "tau" | "tau2" | "tau3";
  metric: string;
  values: string[];
  best: number;
}

interface CapabilityBackbone {
  model: string;
  results: CapabilityResult[];
}

const CAPABILITY_RESULTS: CapabilityBackbone[] = [
  {
    model: "gpt-5.6-sol",
    results: [
      { benchmark: "DeepSearchQA", metric: "Paper F1 (%)", values: ["57.27", "57.74", "58.13", "56.38", "56.63", "57.39", "57.53", "57.02", "57.46"], best: 2 },
      { benchmark: "GDPval", metric: "Elo vs. human", values: ["1129.6", "1070.4", "1053.9", "1053.9", "1085.1", "1093.4", "1063.3", "1059.4", "1041.4"], best: 0 },
      { benchmark: "tau-bench", benchmarkMarkup: "tau", metric: "pass@1 (%)", values: ["60.78", "35.29", "76.79", "77.94", "77.91", "76.39", "55.88", "84.72", "80.56"], best: 7 },
      { benchmark: "tau2-bench", benchmarkMarkup: "tau2", metric: "pass@1 (%)", values: ["63.73", "37.86", "73.47", "73.53", "81.11", "82.67", "65.69", "81.08", "81.94"], best: 5 },
      { benchmark: "tau3-bench", benchmarkMarkup: "tau3", metric: "pass@1 (%)", values: ["61.39", "38.61", "79.25", "76.47", "82.22", "80.00", "62.50", "83.78", "84.00"], best: 8 },
      { benchmark: "Terminal-Bench 2.1", metric: "Success (%)", values: ["74.1", "66.7", "63.0", "66.7", "76.5", "69.1", "67.9", "63.0", "67.9"], best: 4 },
    ],
  },
  {
    model: "glm-5.3",
    results: [
      { benchmark: "DeepSearchQA", metric: "Paper F1 (%)", values: ["33.23", "6.31", "33.58", "6.13", "38.51", "12.95", "5.81", "6.06", "37.05"], best: 4 },
      { benchmark: "GDPval", metric: "Elo vs. human", values: ["1061.0", "1058.8", "1032.0", "1054.9", "1024.5", "1051.1", "1070.4", "1051.1", "1054.9"], best: 6 },
      { benchmark: "tau-bench", benchmarkMarkup: "tau", metric: "pass@1 (%)", values: ["52.17", "15.65", "63.48", "42.61", "62.61", "45.22", "42.61", "58.26", "45.22"], best: 2 },
      { benchmark: "tau2-bench", benchmarkMarkup: "tau2", metric: "pass@1 (%)", values: ["57.89", "23.68", "62.28", "46.49", "58.77", "43.86", "42.98", "59.65", "43.86"], best: 2 },
      { benchmark: "tau3-bench", benchmarkMarkup: "tau3", metric: "pass@1 (%)", values: ["47.37", "20.18", "63.16", "45.61", "50.88", "42.98", "46.49", "57.89", "43.86"], best: 2 },
      { benchmark: "Terminal-Bench 2.1", metric: "Success (%)", values: ["49.4", "49.4", "44.4", "40.7", "53.1", "51.9", "54.3", "48.1", "42.0"], best: 6 },
    ],
  },
];

function CapabilityBenchmarkName({ result }: { result: CapabilityResult }) {
  if (result.benchmarkMarkup === "tau") return <><i>τ</i>-bench</>;
  if (result.benchmarkMarkup === "tau2") return <><i>τ</i><sup>2</sup>-bench</>;
  if (result.benchmarkMarkup === "tau3") return <><i>τ</i><sup>3</sup>-bench</>;
  return result.benchmark;
}

function CapabilityBoundary({ onBack }: { onBack: () => void }) {
  return (
    <main className="capability-boundary-page">
      <header className="capability-boundary-header">
        <button type="button" className="capability-boundary-back" onClick={onBack}>
          <span aria-hidden="true">←</span>
          Home
        </button>
        <div className="capability-boundary-brand">
          <img className="opencompass-logo opencompass-logo-header" src={openCompassLogo} alt="OpenCompass" />
          <div className="brand-product-line">
            <strong>A²E</strong>
            <small>· Evaluation Results</small>
          </div>
        </div>
      </header>
      <section className="capability-boundary-content">
        <p className="capability-boundary-eyebrow">A²E Evaluation Results</p>
        <h1>Agent Capability Boundary</h1>
        <div className="capability-boundary-overview">
          <div className="capability-boundary-copy">
            <p className="capability-boundary-intro">
              This table demonstrates A²E’s ability to run, evaluate, and compare diverse agent harnesses across
              benchmarks and LLMs within a unified pipeline. A²E currently supports 23 benchmarks, with
              results presented here for four frontier evaluations: <span className="capability-benchmark-name">DeepSearchQA</span> for deep web research, <span className="capability-benchmark-name">GDPval</span> for
              economically valuable professional work, the <span className="capability-benchmark-name">τ series</span> for conversational tool use, and <span className="capability-benchmark-name">Terminal-Bench
              2.1</span> for challenging command-line tasks. The table reports official benchmark performance across nine
              agent harnesses and two LLMs. Higher scores are better; the best harness in each row is shown
              in bold with a green highlight.
            </p>
            <p className="capability-range-note">
              <span>Metric range view</span>
              Each petal shows, for one metric, the span from the worst to the best of the nine harnesses after
              averaging over the 23 benchmarks. Petals are grouped by Reasoning, Action, Answer, and Runtime Quality. <code>correctness</code> spans only about 0.42–0.77, indicating limited differences in
              final-answer accuracy, while planning, tool use, and efficiency vary much more widely across harnesses.
            </p>
          </div>
          <figure className="capability-flower">
            <img
              src={capabilityFlower}
              alt="Circular petal chart comparing metric ranges across nine agent harnesses"
            />
          </figure>
        </div>
        <div className="capability-boundary-table-wrap">
          <table className="capability-boundary-table" aria-label="Official agent harness benchmark performance">
            <thead>
              <tr>
                <th scope="col">Benchmark &amp; metric</th>
                {CAPABILITY_HARNESSES.map((lines) => (
                  <th key={lines.join("-")} scope="col">
                    {lines.map((line, index) => (
                      <span key={line}>{index > 0 ? <br /> : null}{line}</span>
                    ))}
                  </th>
                ))}
              </tr>
            </thead>
            {CAPABILITY_RESULTS.map((backbone) => (
              <tbody key={backbone.model}>
                <tr className="capability-backbone-row">
                  <th colSpan={10} scope="rowgroup">
                    <span>LLM</span>
                    <code>{backbone.model}</code>
                  </th>
                </tr>
                {backbone.results.map((result) => (
                  <tr key={result.benchmark}>
                    <th scope="row">
                      <strong><CapabilityBenchmarkName result={result} /></strong>
                      <small>{result.metric}</small>
                    </th>
                    {result.values.map((value, index) => (
                      <td key={`${result.benchmark}-${index}`} className={index === result.best ? "is-best" : undefined}>
                        {index === result.best ? <strong>{value}</strong> : value}
                      </td>
                    ))}
                  </tr>
                ))}
              </tbody>
            ))}
          </table>
        </div>
      </section>
    </main>
  );
}

export default function App() {
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [experiments, setExperiments] = useState<ExperimentSummary[]>([]);
  const [view, setView] = useState<AppView>("home");

  const load = useCallback(async () => {
    setLoading(true);
    setError(null);
    try {
      const exps = await listExperiments();
      setExperiments(exps);
    } catch (e) {
      setError(e instanceof Error ? e.message : String(e));
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    load();
  }, [load]);

  if (view === "capability-boundary") {
    return <CapabilityBoundary onBack={() => setView("home")} />;
  }

  if (view === "home") {
    return (
      <main className="welcome-screen">
        <div className="welcome-grid" aria-hidden="true" />
        <div className="welcome-content">
          <img className="opencompass-logo opencompass-logo-home" src={openCompassLogo} alt="OpenCompass" />
          <div className="welcome-title-line">
            <h1>A²E</h1>
            <p className="welcome-subtitle">· Evaluation Results</p>
          </div>
          <p className="welcome-overview">
            This interface presents standardized execution traces and multidimensional evaluation results produced
            by A²E (Agent Auditing Engine).
          </p>
          <p className="welcome-intro">
            Choose a benchmark, agent, and run to inspect sample-level trajectories and compare evaluation results
            across correctness, safety, and efficiency.
          </p>
          <nav className="welcome-resources" aria-label="Project resources">
            <a href="https://arxiv.org/abs/2608.07346" target="_blank" rel="noreferrer">
              <span>Paper</span>
              <small>arXiv</small>
            </a>
            <a href="https://github.com/datamllab/A2E" target="_blank" rel="noreferrer">
              <span>GitHub</span>
              <small>Source</small>
            </a>
            <a
              href="https://colab.research.google.com/github/datamllab/A2E/blob/main/notebooks/a2e_quickstart.ipynb"
              target="_blank"
              rel="noreferrer"
            >
              <span>Colab</span>
              <small>Notebook</small>
            </a>
            <a href="https://huggingface.co/papers/2608.07346" target="_blank" rel="noreferrer">
              <span>HuggingFace</span>
              <small>Paper page</small>
            </a>
          </nav>
          <div className="welcome-actions">
            <button
              type="button"
              className="welcome-enter"
              onClick={() => setView("workspace")}
              disabled={loading}
            >
              {loading ? "Loading experiments..." : "Enter workspace"}
              <span aria-hidden="true">→</span>
            </button>
            <button
              type="button"
              className="welcome-enter welcome-capability-boundary"
              onClick={() => setView("capability-boundary")}
            >
              Agent Capability Boundary
              <span aria-hidden="true">↗</span>
            </button>
          </div>
          <div className="welcome-guide" aria-label="Workspace sections">
            <span><b>01</b> Tasks</span>
            <span><b>02</b> Traces</span>
            <span><b>03</b> Evaluation</span>
          </div>
        </div>
      </main>
    );
  }

  if (loading) {
    return (
      <div className="overlay">
        <div className="overlay-card">
          <div className="spinner" />
          <p className="overlay-msg">Loading benchmarks…</p>
        </div>
      </div>
    );
  }

  if (error) {
    return (
      <div className="overlay">
        <div className="overlay-card">
          <p className="overlay-msg">{error}</p>
          <button type="button" className="retry" onClick={load}>
            Retry
          </button>
        </div>
      </div>
    );
  }

  return <Deck experiments={experiments} onBack={() => setView("home")} />;
}
