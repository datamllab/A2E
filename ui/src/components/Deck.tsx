import { useCallback, useEffect, useMemo, useRef, useState } from "react";
import { getExperimentContext, getExperimentJson } from "../api/experiments";
import type { AgentInfo, ExperimentContext, ExperimentRecord, ExperimentSummary } from "../api/types";
import { benchmarksFromExperiments, benchExperiments, benchKey, normKey, type Benchmark } from "../data/benchmarks";
import { useDeck } from "../hooks/useDeck";
import {
  agentsForExperiments,
  defaultSelection,
  experimentsForAgent,
  hasEvaluationResults,
  newestExperimentsFirst,
} from "../utils/eval";
import {
  dbAgentFromExperiment,
  dbJudgeModelNamesForSelection,
  dbTestedAgentModelNamesForSelection,
} from "../utils/dbIdentity";
import { BenchmarkTree } from "./BenchmarkTree";
import { EvalPanel } from "./EvalPanel";
import { TraceControls } from "./TraceControls";
import { TracePanel } from "./TracePanel";

interface Props {
  experiments: ExperimentSummary[];
}

function formatRunTime(value?: string): string {
  if (!value) return "unknown time";
  return String(value).replace("T", " ").replace(/\.\d+Z?$/, "").replace(/Z$/, "").slice(0, 19);
}

export function Deck({ experiments }: Props) {
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
  const [selectionLoading, setSelectionLoading] = useState(false);
  const [runScanLoading, setRunScanLoading] = useState(false);
  const [evaluatedRuns, setEvaluatedRuns] = useState<ExperimentSummary[]>([]);
  const bootedRef = useRef(false);
  const selectionRequestRef = useRef(0);
  const runScanRequestRef = useRef(0);
  const recordsCacheRef = useRef(new Map<string, ExperimentRecord[]>());
  const recordsRequestRef = useRef(new Map<string, Promise<ExperimentRecord[]>>());

  const benchmarkExperiments = useMemo(() => {
    return selectedBench ? benchExperiments(selectedBench, experiments) : [];
  }, [experiments, selectedBench]);

  const agentOptions = useMemo(() => {
    const available = agentsForExperiments(benchmarkExperiments);
    if (!selectedAgent || available.some((agent) => agent.id === selectedAgent.id)) {
      return available;
    }
    // Keep a manually selected agent visible even when the newly selected
    // benchmark has no run for it. Only the Agent wheel may change the agent.
    return [selectedAgent, ...available];
  }, [benchmarkExperiments, selectedAgent]);

  const agentRunCandidates = useMemo(
    () => newestExperimentsFirst(experimentsForAgent(benchmarkExperiments, selectedAgent)),
    [benchmarkExperiments, selectedAgent],
  );

  const runOptions = useMemo(
    () =>
      evaluatedRuns.map((exp) => ({
        exp,
        label: formatRunTime(exp.created_at),
      })),
    [evaluatedRuns],
  );

  const showToast = (msg: string) => {
    setToast(msg);
    setTimeout(() => setToast(""), 1800);
  };

  const getExperimentRecords = useCallback((experimentId: string) => {
    const cached = recordsCacheRef.current.get(experimentId);
    if (cached) return Promise.resolve(cached);

    const pending = recordsRequestRef.current.get(experimentId);
    if (pending) return pending;

    const request = getExperimentJson(experimentId)
      .then((nextRecords) => {
        recordsCacheRef.current.set(experimentId, nextRecords);
        return nextRecords;
      })
      .finally(() => {
        recordsRequestRef.current.delete(experimentId);
      });
    recordsRequestRef.current.set(experimentId, request);
    return request;
  }, []);

  const handleSelect = useCallback(
    async (b: Benchmark, exp: ExperimentSummary, agent: AgentInfo | null, navigate = true) => {
      const requestId = ++selectionRequestRef.current;
      const dbAgent = dbAgentFromExperiment(exp) ?? agent;

      // Commit the selector state immediately and clear the previous payload.
      // This keeps Agent, Run, Trace and Eval on the same experiment while the
      // new experiment is loading instead of showing the previous payload.
      setSelectedBench(b);
      setSelectedExp(exp);
      setRecords([]);
      setContext(null);
      setSelectedKey(normKey(benchKey(b)));
      setActiveSample(0);
      setSelectionLoading(true);
      if (navigate) setPanel(1);
      showToast(`Loading ${b.name}${dbAgent ? ` · ${dbAgent.label}` : ""} …`);

      try {
        const recs = await getExperimentRecords(exp.id);
        if (requestId !== selectionRequestRef.current) return;
        if (!hasEvaluationResults(recs)) {
          setEvaluatedRuns((current) => current.filter((run) => run.id !== exp.id));
          setSelectedExp(null);
          showToast(`${b.name}: This run has no evaluation results`);
          return;
        }

        // Trace data is already usable here. Context is supplementary and
        // must not prevent a valid run from appearing if its request fails.
        setRecords(recs);
        setSelectionLoading(false);
        const fullCtx = await getExperimentContext(exp.id, recs);
        if (requestId !== selectionRequestRef.current) return;
        setContext(fullCtx);
      } catch (e) {
        if (requestId === selectionRequestRef.current) {
          showToast(`Failed to load: ${e instanceof Error ? e.message : String(e)}`);
        }
      } finally {
        if (requestId === selectionRequestRef.current) setSelectionLoading(false);
      }
    },
    [getExperimentRecords, setPanel],
  );

  const handleAgentChange = useCallback(
    (agent: AgentInfo) => {
      if (!selectedBench) return;
      if (agent.id === selectedAgent?.id) return;
      selectionRequestRef.current += 1;
      runScanRequestRef.current += 1;
      setSelectedAgent(agent);
      setSelectedExp(null);
      setRecords([]);
      setContext(null);
      setEvaluatedRuns([]);
      setActiveSample(0);
      setSelectionLoading(false);
      setRunScanLoading(true);
    },
    [selectedAgent?.id, selectedBench],
  );

  const handleBenchmarkChange = useCallback(
    (
      benchmark: Benchmark,
      fallbackExperiment: ExperimentSummary,
      fallbackAgent: AgentInfo | null,
      navigate = true,
    ) => {
      selectionRequestRef.current += 1;
      runScanRequestRef.current += 1;
      setSelectedBench(benchmark);
      setSelectedExp(null);
      setSelectedAgent((current) => current ?? fallbackAgent ?? dbAgentFromExperiment(fallbackExperiment));
      setRecords([]);
      setContext(null);
      setEvaluatedRuns([]);
      setSelectedKey(normKey(benchKey(benchmark)));
      setActiveSample(0);
      setSelectionLoading(false);
      setRunScanLoading(true);
      if (navigate) setPanel(1);
    },
    [setPanel],
  );

  useEffect(() => {
    if (bootedRef.current || !experiments.length) return;
    bootedRef.current = true;
    const sel = defaultSelection(experiments, benchmarks);
    if (sel) handleBenchmarkChange(sel.b, sel.exp, sel.agent, false);
  }, [experiments, benchmarks, handleBenchmarkChange]);

  useEffect(() => {
    const requestId = ++runScanRequestRef.current;
    if (!selectedBench || !selectedAgent || !agentRunCandidates.length) {
      setEvaluatedRuns([]);
      setRunScanLoading(false);
      return;
    }

    setRunScanLoading(true);
    void Promise.all(
      agentRunCandidates.map(async (experiment) => {
        try {
          const experimentRecords = await getExperimentRecords(experiment.id);
          return hasEvaluationResults(experimentRecords) ? experiment : null;
        } catch {
          return null;
        }
      }),
    ).then((results) => {
      if (requestId !== runScanRequestRef.current) return;
      const nextRuns = results.filter((experiment): experiment is ExperimentSummary => Boolean(experiment));
      setEvaluatedRuns(nextRuns);
      setRunScanLoading(false);

      const nextExperiment = nextRuns[0];
      if (nextExperiment) {
        void handleSelect(selectedBench, nextExperiment, selectedAgent, false);
      }
    });
  }, [agentRunCandidates, getExperimentRecords, handleSelect, selectedAgent, selectedBench]);

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
          {selectedBench ? (
            <TraceControls
              benchmark={selectedBench}
              runOptions={runOptions}
              agentOptions={agentOptions}
              selectedAgent={selectedAgent}
              selectedExperimentId={selectedExp?.id}
              onRunChange={(exp) =>
                handleSelect(selectedBench, exp, dbAgentFromExperiment(exp), false)
              }
              onAgentChange={handleAgentChange}
            />
          ) : null}
          <div className="counter lab-logo" data-sample={records.length ? `${activeSample + 1}/${records.length}` : ""}>
            <img src={`${window.Config?.basename ?? ""}/ailab-logo.png`} alt="" />
          </div>
        </div>
        <nav className="segmented" ref={segRef} aria-label="Switch view">
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
          onSelect={handleBenchmarkChange}
          onToast={showToast}
        />
        <TracePanel
          records={records}
          benchmarkName={selectedBench?.name ?? null}
          projectName={selectedExp?.project_name ?? context?.experiment?.project_name}
          emptyMessage={
            runScanLoading
              ? "Checking evaluated runs…"
              : selectionLoading
              ? "Loading the selected evaluation…"
              : selectedExp
                ? "No samples for the selected run"
                : selectedAgent
                  ? "No evaluated runs for the selected agent"
                  : undefined
          }
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
          judgeModel={dbJudgeModelNamesForSelection(selectedExp, context, records).join(", ")}
          loading={runScanLoading || selectionLoading}
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
