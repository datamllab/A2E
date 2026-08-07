import { benchExperiments, normKey, benchKey, type Benchmark } from "../data/benchmarks";
import type { AgentInfo, ExperimentSummary } from "../api/types";
import { benchDefaultSelection } from "../utils/eval";
import { esc } from "../utils/format";
import { Fragment, useState, useMemo } from "react";

const CATS = ["Coding", "Conversational", "Research", "Computer use"];
const CAPS = ["Skill", "Memory", "Tool"];

const DIFF_LABEL: Record<string, [string, string]> = {
  found: ["Foundational", "#8e8e93"],
  med: ["Medium", "#2bc0a8"],
  hard: ["Hard", "#ff9f0a"],
  front: ["Frontier", "#ff375f"],
};

function domainColumn(benchmark: Benchmark): number {
  const category = benchmark.cat;
  // Every database benchmark must be present on Domain × Year. The inference
  // layer normally assigns 0..3; this fallback prevents malformed/unknown
  // presentation metadata from silently dropping a card from the grid.
  return Number.isInteger(category) && Number(category) >= 0 && Number(category) < CATS.length
    ? Number(category)
    : 2;
}

const TREE_FACES = [
  { title: "Domain × Year", cols: CATS, colOf: domainColumn },
  { title: "Capability Dimension · Skill / Memory / Tool", cols: CAPS, colOf: (b: Benchmark) => b.dim },
] as const;

interface Props {
  benchmarks: Benchmark[];
  experiments: ExperimentSummary[];
  selectedKey: string | null;
  onSelect: (b: Benchmark, exp: ExperimentSummary, agent: AgentInfo | null) => void;
  onToast: (msg: string) => void;
}

function BenchGrid({
  face,
  benchmarks,
  years,
  experiments,
  selectedKey,
  onSelect,
  onToast,
}: {
  face: (typeof TREE_FACES)[number];
  benchmarks: Benchmark[];
  years: string[];
  experiments: ExperimentSummary[];
  selectedKey: string | null;
  onSelect: Props["onSelect"];
  onToast: Props["onToast"];
}) {
  return (
    <div className="bench-wrap">
      <div
        className="bench-grid"
        style={{ gridTemplateColumns: `44px repeat(${face.cols.length}, minmax(120px, 1fr))` }}
      >
        <div />
        {face.cols.map((c) => (
          <div key={c} className="bench-cat">
            {c}
          </div>
        ))}
        {years.map((y) => (
          <Fragment key={y}>
            <div className="bench-year">{y}</div>
            {face.cols.map((_, ci) => (
              <div key={`${y}-${ci}`} className="bench-cell">
                {benchmarks.filter((b) => face.colOf(b) === ci && b.year === y).map((b) => {
                  const exps = benchExperiments(b, experiments);
                  const key = normKey(benchKey(b));
                  return (
                    <button
                      key={key}
                      type="button"
                      className={`bench-chip d-${b.diff}${exps.length ? " avail" : ""}${selectedKey === key ? " sel" : ""}`}
                      title={b.date ? `${b.name} · released ${b.date}` : b.name}
                      onClick={() => {
                        if (exps.length) {
                          const sel = benchDefaultSelection(b, experiments);
                          if (sel) onSelect(sel.b, sel.exp, sel.agent);
                        } else {
                          onToast(`${b.name}: No data available`);
                        }
                      }}
                    >
                      <span className="bench-name">{b.name}</span>
                      {b.date ? <span className="bench-date">{b.date}</span> : null}
                    </button>
                  );
                })}
              </div>
            ))}
          </Fragment>
        ))}
      </div>
    </div>
  );
}

function CubeScene({
  benchmarks,
  experiments,
  selectedKey,
  onSelect,
  onToast,
}: Props) {
  const [faceIdx, setFaceIdx] = useState(0);
  const [spin, setSpin] = useState<{ from: number; to: number; key: number } | null>(null);
  const years = useMemo(() => {
    return [...new Set(benchmarks.map((b) => b.year).filter(Boolean))].sort();
  }, [benchmarks]);

  const flip = () => {
    if (spin) return;
    const next = (faceIdx + 1) % TREE_FACES.length;
    setSpin({ from: faceIdx, to: next, key: Date.now() });
    setFaceIdx(next);
  };

  return (
    <>
      <div className="cube-ctrl">
        <span className="cube-face-title">{TREE_FACES[faceIdx].title}</span>
        <button type="button" className="cube-flip" onClick={flip}>
          Rotate ↻
        </button>
      </div>
      <div className={`cube-scene${spin ? " is-spinning" : ""}`}>
        <div className="cube-static" aria-hidden={Boolean(spin)}>
          <BenchGrid
            face={TREE_FACES[faceIdx]}
            benchmarks={benchmarks}
            years={years}
            experiments={experiments}
            selectedKey={selectedKey}
            onSelect={onSelect}
            onToast={onToast}
          />
        </div>
        {spin ? (
          <div
            key={spin.key}
            className="cube-anim"
            onAnimationEnd={(e) => {
              if (e.currentTarget === e.target) setSpin(null);
            }}
          >
            {[spin.from, spin.to].map((idx, i) => (
              <div key={`${spin.key}-${idx}-${i}`} className={`cube-anim-face ${i === 0 ? "front" : "next"}`}>
              <BenchGrid
                face={TREE_FACES[idx]}
                benchmarks={benchmarks}
                years={years}
                experiments={experiments}
                selectedKey={selectedKey}
                onSelect={onSelect}
                onToast={onToast}
              />
              </div>
          ))}
          </div>
        ) : null}
      </div>
    </>
  );
}

export function BenchmarkTree({ benchmarks, experiments, selectedKey, onSelect, onToast }: Props) {
  const linked = benchmarks.filter((b) => benchExperiments(b, experiments).length).map((b) => b.name);
  const experimentNoun = experiments.length === 1 ? "experiment" : "experiments";
  const harnessNoun = linked.length === 1 ? "harness" : "harnesses";

  return (
    <article className="panel bench">
      <div className="panel-inner">
        <p className="kicker">Task</p>
        <h2 className="bench-title">Agent benchmark tree</h2>
        <p className="muted" style={{ margin: "-4px 0 4px", fontSize: 12 }}>
          Current database: {experiments.length} {experimentNoun}
          {linked.length ? ` · ${linked.length} ${harnessNoun}: ${esc(linked.join(", "))}` : " · No experiment data"}
        </p>
        <CubeScene
          benchmarks={benchmarks}
          experiments={experiments}
          selectedKey={selectedKey}
          onSelect={onSelect}
          onToast={onToast}
        />
        <div className="bench-legend">
          {Object.values(DIFF_LABEL).map(([label, color]) => (
            <span key={label}>
              <i style={{ background: color }} />
              {label}
            </span>
          ))}
        </div>
      </div>
    </article>
  );
}
