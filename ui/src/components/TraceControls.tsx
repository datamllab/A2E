import { useCallback, useRef } from "react";
import type { AgentInfo, ExperimentSummary } from "../api/types";
import type { Benchmark } from "../data/benchmarks";
import { esc } from "../utils/format";

function displayExperimentId(value?: string): string {
  if (!value) return "—";
  try {
    const decoded = atob(value);
    const match = decoded.match(/^Experiment:(.+)$/);
    if (match?.[1]) return match[1];
    return decoded || value;
  } catch {
    return value;
  }
}

function wheelItems(items: string[], idx: number) {
  const values = items.length ? items : ["—"];
  const n = values.length;
  const row = (offset: number, cls: string) => (
    <div key={`${offset}-${cls}`} className={`trace-wheel-item ${cls}`} title={values[(idx + offset + n) % n]}>
      {esc(values[(idx + offset + n) % n])}
    </div>
  );
  if (n === 1) {
    return (
      <>
        <div className="trace-wheel-item spacer" />
        {row(0, "active")}
        <div className="trace-wheel-item spacer" />
      </>
    );
  }
  return (
    <>
      {row(-1, "prev")}
      {row(0, "active")}
      {row(1, "next")}
    </>
  );
}

interface RunOption {
  label: string;
  exp: ExperimentSummary;
}

interface Props {
  benchmark: Benchmark;
  runOptions: RunOption[];
  agentOptions: AgentInfo[];
  selectedAgent: AgentInfo | null;
  selectedExperimentId?: string;
  onRunChange: (exp: ExperimentSummary) => void;
  onAgentChange: (agent: AgentInfo) => void;
}

export function TraceControls({
  benchmark,
  runOptions,
  agentOptions,
  selectedAgent,
  selectedExperimentId,
  onRunChange,
  onAgentChange,
}: Props) {
  const lockRef = useRef(false);

  const runLabels = runOptions.map((item) => item.label);
  const selectedRunIndex = runOptions.findIndex((item) => item.exp.id === selectedExperimentId);
  const runIndex = Math.max(0, selectedRunIndex);
  const agentLabels = agentOptions.map((agent) => agent.label);
  const selectedAgentIndex = agentOptions.findIndex((agent) => agent.id === selectedAgent?.id);
  const agentIndex = Math.max(0, selectedAgentIndex);
  const cycleByWheel = useCallback(
    (e: React.WheelEvent, field: HTMLElement, onStep: (dir: number) => void) => {
      const delta = Math.abs(e.deltaY) >= Math.abs(e.deltaX) ? e.deltaY : e.deltaX;
      if (!delta) return;
      e.preventDefault();
      if (lockRef.current) return;
      lockRef.current = true;
      field.classList.add("scrolling");
      onStep(delta > 0 ? 1 : -1);
      window.setTimeout(() => {
        lockRef.current = false;
        field.classList.remove("scrolling");
      }, 140);
    },
    [],
  );

  return (
    <div className="trace-controls">
      <div className="trace-selector-row">
        <div className="trace-select-field trace-bench">
          <span>Benchmark</span>
          <strong>{benchmark.name}</strong>
        </div>
        <div className="trace-select-field trace-experiment-id" title={selectedExperimentId ?? "—"}>
          <span>Experiment ID</span>
          <strong>{displayExperimentId(selectedExperimentId)}</strong>
        </div>
        {agentOptions.length ? (
          <div
            className="trace-select-field trace-wheel trace-select-agent"
            tabIndex={0}
            aria-label="Scroll to select agent"
            onWheel={(e) => {
              cycleByWheel(e, e.currentTarget, (dir) => {
                const idx = Math.max(0, selectedAgentIndex);
                const next = agentOptions[(idx + dir + agentOptions.length) % agentOptions.length];
                onAgentChange(next);
              });
            }}
            onKeyDown={(e) => {
              if (e.key !== "ArrowDown" && e.key !== "ArrowUp") return;
              e.preventDefault();
              const dir = e.key === "ArrowDown" ? 1 : -1;
              e.currentTarget.dispatchEvent(new WheelEvent("wheel", { deltaY: dir, bubbles: true, cancelable: true }));
            }}
          >
            <span>Agent</span>
            <div className="trace-wheel-window">
              <div className="trace-wheel-track">{wheelItems(agentLabels, agentIndex)}</div>
            </div>
          </div>
        ) : null}
        {runOptions.length ? (
          <div
            className="trace-select-field trace-wheel trace-select-run"
            tabIndex={0}
            aria-label="Scroll to select evaluation run"
            onWheel={(e) => {
              cycleByWheel(e, e.currentTarget, (dir) => {
                const idx = Math.max(0, selectedRunIndex);
                const next = runOptions[(idx + dir + runOptions.length) % runOptions.length];
                onRunChange(next.exp);
              });
            }}
            onKeyDown={(e) => {
              if (e.key !== "ArrowDown" && e.key !== "ArrowUp") return;
              e.preventDefault();
              const dir = e.key === "ArrowDown" ? 1 : -1;
              e.currentTarget.dispatchEvent(new WheelEvent("wheel", { deltaY: dir, bubbles: true, cancelable: true }));
            }}
          >
            <span>Run</span>
            <div className="trace-wheel-window">
              <div className="trace-wheel-track">{wheelItems(runLabels, runIndex)}</div>
            </div>
          </div>
        ) : null}
      </div>
    </div>
  );
}
