import { useCallback, useEffect, useMemo, useRef, useState } from "react";
import { getExperimentContext, getExperimentJson } from "../api/experiments";
import type { AgentInfo, ExperimentContext, ExperimentRecord, ExperimentSummary } from "../api/types";
import { benchmarksFromExperiments, benchExperiments, benchKey, normKey, type Benchmark } from "../data/benchmarks";
import { useDeck } from "../hooks/useDeck";
import { defaultSelection } from "../utils/eval";
import { applyModelPricing } from "../utils/pricing";
import {
  dbAgentFromExperiment,
  dbTestedAgentModelNamesForSelection,
} from "../utils/dbIdentity";
import { BenchmarkTree } from "./BenchmarkTree";
import { EvalPanel } from "./EvalPanel";
import { TraceControls } from "./TraceControls";
import { TracePanel } from "./TracePanel";
import openCompassLogo from "../assets/opencompass.png";

interface Props {
  experiments: ExperimentSummary[];
  onBack: () => void;
}

function formatRunTime(value?: string): string {
  if (!value) return "unknown time";
  return String(value).replace("T", " ").replace(/\.\d+Z?$/, "").replace(/Z$/, "").slice(0, 16);
}

export function Deck({ experiments, onBack }: Props) {
  const { deckRef, segRef, trackRef, activePanel, setPanel, panels } = useDeck();
  const benchmarks = useMemo(() => benchmarksFromExperiments(experiments), [experiments]);
  const [selectedBench, setSelectedBench] = useState<Benchmark | null>(null);
  const [selectedExp, setSelectedExp] = useState<ExperimentSummary | null>(null);
  const [selectedAgent, setSelectedAgent] = useState<AgentInfo | null>(null);
  const [records, setRecords] = useState<ExperimentRecord[]>([]);
  const [context, setContext] = useState<ExperimentContext | null>(null);
  const [selectedKey, setSelectedKey] = useState<string | null>(null);
  const [toast, setToast] = useState("");
  const [activeSample, setActiveSample] = useState(0);
  const bootedRef = useRef(false);

  const agentOptions = useMemo(() => {
    if (!selectedBench) return [];
    const unique = new Map<string, { exp: ExperimentSummary; agent: AgentInfo }>();
    for (const exp of benchExperiments(selectedBench, experiments)) {
      const agent = dbAgentFromExperiment(exp);
      if (agent && !unique.has(agent.id)) unique.set(agent.id, { exp, agent });
    }
    return [...unique.values()];
  }, [experiments, selectedBench]);

  const runOptions = useMemo(() => {
    if (!selectedBench || !selectedAgent) return [];
    const newestFirst = benchExperiments(selectedBench, experiments).filter((exp) => {
      const agent = dbAgentFromExperiment(exp);
      return agent?.id === selectedAgent.id;
    });
    return [...newestFirst]
      .sort((a, b) => String(a.created_at ?? "").localeCompare(String(b.created_at ?? "")))
      .map((exp) => ({
        exp,
        agent: dbAgentFromExperiment(exp),
        label: formatRunTime(exp.created_at),
      }));
  }, [experiments, selectedBench, selectedAgent]);

  const showToast = (msg: string) => {
    setToast(msg);
    setTimeout(() => setToast(""), 1800);
  };

  const handleSelect = useCallback(
    async (b: Benchmark, exp: ExperimentSummary, agent: AgentInfo | null, navigate = true) => {
      showToast(`Loading ${b.name}${agent ? ` · ${agent.label}` : ""} …`);
      try {
        const recs = await getExperimentJson(exp.id);
        if (!recs.length) {
          showToast(`${b.name}: No samples`);
          return;
        }
        const fullCtx = await getExperimentContext(exp.id, recs);
        const testedModel = dbTestedAgentModelNamesForSelection(exp, fullCtx, recs)[0];
        const pricedRecords = applyModelPricing(recs, testedModel);
        const dbAgent = agent ?? dbAgentFromExperiment(exp);
        setSelectedBench(b);
        setSelectedExp(exp);
        setSelectedAgent(dbAgent);
        setRecords(pricedRecords);
        setContext(fullCtx);
        setSelectedKey(normKey(benchKey(b)));
        setActiveSample(0);
        if (navigate) setPanel(1);
      } catch (e) {
        showToast(`Load failed: ${e instanceof Error ? e.message : String(e)}`);
      }
    },
    [setPanel],
  );

  useEffect(() => {
    if (bootedRef.current || !experiments.length) return;
    bootedRef.current = true;
    const sel = defaultSelection(experiments, benchmarks);
    if (sel) void handleSelect(sel.b, sel.exp, sel.agent, false);
  }, [experiments, benchmarks, handleSelect]);

  useEffect(() => {
    const onKey = (e: KeyboardEvent) => {
      if (activePanel !== 1 || !records.length) return;
      if (e.key !== "ArrowDown" && e.key !== "ArrowUp") return;
      e.preventDefault();
      setActiveSample((cur) => {
        const next = Math.max(0, Math.min(records.length - 1, cur + (e.key === "ArrowDown" ? 1 : -1)));
        return next;
      });
      setPanel(1, false);
    };
    window.addEventListener("keydown", onKey);
    return () => window.removeEventListener("keydown", onKey);
  }, [activePanel, records.length, setPanel]);

  return (
    <>
      <header className="topbar">
        <div className="topbar-inner">
          <button type="button" className="topbar-home" onClick={onBack}>
            <span aria-hidden="true">←</span>
            Home
          </button>
          {selectedBench && records.length > 0 ? (
            <TraceControls
              benchmark={selectedBench}
              runOptions={runOptions}
              agentOptions={agentOptions}
              selectedAgent={selectedAgent}
              selectedExperimentId={selectedExp?.id}
              onRunChange={(exp) => handleSelect(selectedBench, exp, selectedAgent, false)}
              onAgentChange={(exp, agent) => handleSelect(selectedBench, exp, agent, false)}
            />
          ) : null}
          <div className="topbar-brand">
            <img className="opencompass-logo opencompass-logo-header" src={openCompassLogo} alt="OpenCompass" />
            <div className="brand-product-line">
              <strong>A²E</strong>
              <small>· Evaluation Results</small>
            </div>
          </div>
        </div>
        <nav className="segmented" ref={segRef} aria-label="View switcher">
          <div className="seg-track" ref={trackRef}>
            {panels.map((label, i) => (
              <button
                key={label}
                type="button"
                data-panel={i}
                className={`seg${activePanel === i ? " active" : ""}`}
                onClick={() => setPanel(i)}
              >
                {label}
              </button>
            ))}
          </div>
        </nav>
      </header>

      <main className="pager" id="deck" ref={deckRef}>
        <BenchmarkTree
          benchmarks={benchmarks}
          experiments={experiments}
          selectedKey={selectedKey}
          onSelect={(b, exp, agent) => handleSelect(b, exp, agent)}
        />
        <TracePanel
          records={records}
          benchmarkName={selectedBench?.name ?? null}
          projectName={selectedExp?.project_name ?? context?.experiment?.project_name}
          activeSample={activeSample}
          onActiveSampleChange={setActiveSample}
          onGoTask={() => setPanel(0)}
          onGoEval={() => setPanel(2)}
        />
        <EvalPanel
          benchmark={selectedBench}
          records={records}
          context={context}
          agent={selectedAgent}
          experimentDatasetName={selectedExp?.dataset_name}
          projectName={selectedExp?.project_name}
          testedAgentModel={dbTestedAgentModelNamesForSelection(selectedExp, context, records).join(", ")}
        />
      </main>

      <aside className="dots" id="dots" aria-hidden="true">
        {records.map((_, i) => (
          <span
            key={i}
            className={`dot${i === activeSample ? " active" : ""}`}
            onClick={() => {
              setPanel(1);
              setActiveSample(i);
            }}
          />
        ))}
      </aside>

      <div className={`toast${toast ? " show" : ""}`}>{toast}</div>
    </>
  );
}
