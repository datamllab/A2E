import { useCallback, useEffect, useRef, useState } from "react";
import { getTraceSpans } from "../api/spans";
import type { ExperimentRecord } from "../api/types";
import { BraceBig } from "./BraceBig";
import { SpanTree } from "./SpanTree";
import { pretty } from "../utils/format";
import { fmtMs, sampleScore } from "../utils/eval";
import { getMetricDescription, metricRangeClass } from "../utils/metricDescriptions";
import { MetricTooltip } from "./MetricTooltip";

function statusPill(status: string) {
  const s = String(status || "ok").toLowerCase();
  const cls = s === "error" || s === "failed" ? "bad" : s === "ok" || s === "success" ? "good" : "";
  return <span className={`pill status ${cls}`}>{s}</span>;
}

type TraceMetricGroupId = "efficiency" | "safety" | "accuracy";

const TRACE_METRIC_GROUPS: Array<{ id: TraceMetricGroupId; label: string; metrics: string[] }> = [
  {
    id: "efficiency",
    label: "Efficiency",
    metrics: ["total_token_usage", "cost", "answer_cost", "turn_count", "elapsed_time"],
  },
  {
    id: "safety",
    label: "Safety",
    metrics: [
      "hallucination",
      "privacy_leakage",
      "unauthorized_action",
      "harmful_action",
      "failure_transparency",
      "prompt_injection_resilience",
    ],
  },
  {
    id: "accuracy",
    label: "Accuracy",
    metrics: [
      "correctness",
      "instruction_following",
      "llm_judge",
      "task_succeeded",
      "execution_completion",
      "error_absence",
    ],
  },
];

function scoreForMetric(rec: ExperimentRecord, name: string): number | null {
  const target = name.toLowerCase();
  const score = (rec.annotations ?? []).find((a) => String(a.name).toLowerCase() === target)?.score;
  return typeof score === "number" && Number.isFinite(score) ? score : null;
}

function numericValue(value: unknown): number | null {
  if (typeof value === "number" && Number.isFinite(value)) return value;
  if (typeof value === "string" && value.trim()) {
    const parsed = Number(value);
    return Number.isFinite(parsed) ? parsed : null;
  }
  return null;
}

function ToolFallback({ out }: { out: Record<string, unknown> }) {
  const tools = Array.isArray(out.tool_calls) ? out.tool_calls : [];
  if (!tools.length) return <p className="muted">No trace available</p>;
  return (
    <div className="timeline">
      {tools.map((t, i) => (
        <div key={i} className="tl-item">
          <div className="tl-name">{typeof t === "string" ? t : String((t as { name?: string }).name ?? pretty(t))}</div>
          <div className="tl-sub">step {i + 1}</div>
        </div>
      ))}
    </div>
  );
}

function CollapsibleBrief({ label, text }: { label: string; text: string }) {
  const [expanded, setExpanded] = useState(false);
  return (
    <div className={`card sample-brief-card collapsible-brief${expanded ? " expanded" : ""}`}>
      <div className="brief-head">
        <p className="card-label">{label}</p>
      </div>
      <p className={`sample-copy brief-copy${expanded ? "" : " collapsed"}`}>{text}</p>
      <button
        type="button"
        className="brief-toggle"
        aria-label={expanded ? `Collapse ${label}` : `Expand ${label}`}
        aria-expanded={expanded}
        title={expanded ? "Collapse" : "Expand"}
        onClick={() => setExpanded((v) => !v)}
      >
        <span aria-hidden="true">{expanded ? "▴" : "▾"}</span>
      </button>
    </div>
  );
}

function SampleCard({
  rec,
  index,
  total,
  projectName,
  open,
  onToggle,
}: {
  rec: ExperimentRecord;
  index: number;
  total: number;
  projectName?: string;
  open: boolean;
  onToggle: () => void;
}) {
  const [spans, setSpans] = useState<null | Awaited<ReturnType<typeof getTraceSpans>>>(null);
  const [loading, setLoading] = useState(false);
  const [spanError, setSpanError] = useState<string | null>(null);
  const out = (rec.output ?? {}) as Record<string, unknown>;
  const input = (rec.input ?? {}) as Record<string, unknown>;
  const status = String(out.status ?? (rec.error ? "error" : "ok"));
  const instruction = String(input.instruction ?? input.question ?? pretty(input));
  const traceId = rec.trace_id || String(out.trace_id ?? "");
  const score = sampleScore(rec);
  const turnValue = numericValue(out.turns);
  const toolCallCount = Array.isArray(out.tool_calls) ? out.tool_calls.length : 0;
  const latencyDescription = [
    "- Meaning: End-to-end runtime duration for this sample.",
    "- Source: rec.latency_ms from the run record.",
    "- Display: formatted seconds or milliseconds; lower is usually better.",
  ].join("\n");
  const avgScoreDescription = [
    "- Meaning: Average score across numeric annotations available on this sample.",
    "- Calculation: Arithmetic mean of this sample's annotation scores.",
    "- Display: 0 to 1 when the underlying metrics are normalized; higher is better.",
  ].join("\n");
  const [metricGroup, setMetricGroup] = useState<TraceMetricGroupId>("efficiency");
  const selectedMetricGroup = TRACE_METRIC_GROUPS.find((group) => group.id === metricGroup) ?? TRACE_METRIC_GROUPS[0];
  const visibleScores = selectedMetricGroup.metrics
    .map((name) => [name, scoreForMetric(rec, name)] as const)
    .filter((item): item is readonly [string, number] => item[1] != null);

  useEffect(() => {
    setSpans(null);
    setSpanError(null);
    setLoading(false);
  }, [traceId, projectName]);

  useEffect(() => {
    if (!open) return;
    if (!traceId || !projectName) return;
    if (spans !== null) return;
    let cancelled = false;
    setLoading(true);
    setSpanError(null);
    getTraceSpans(projectName, traceId)
      .then((next) => {
        if (!cancelled) setSpans(next);
      })
      .catch((err) => {
        if (!cancelled) {
          setSpans(null);
          setSpanError(err instanceof Error ? err.message : String(err));
        }
      })
      .finally(() => {
        if (!cancelled) setLoading(false);
      });
    return () => {
      cancelled = true;
    };
  }, [open, spans, traceId, projectName]);

  return (
    <div className={`scard-card${open ? " open" : ""}`} data-sample-index={index}>
      <div
        className="sc-head"
        onClick={onToggle}
        onKeyDown={(e) => {
          if (e.key === "Enter" || e.key === " ") {
            e.preventDefault();
            onToggle();
          }
        }}
        role="button"
        tabIndex={0}
      >
        <span className="sc-twist">▸</span>
        <div className="sc-head-text">
          <div className="sc-title">
            Sample {index + 1} / {total}
          </div>
          <div className="sc-sub">{instruction}</div>
        </div>
        {statusPill(status)}
      </div>
      {open ? (
        <div className="sc-body">
          <div className="card run-overview">
            <div className="run-title">
              <div className="run-title-main">Metric</div>
              {statusPill(status)}
            </div>
            <div className="run-stats">
              <div className="run-stat has-metric-tooltip">
                <div className="run-stat-k">Latency</div>
                <div className="run-stat-v">{rec.latency_ms != null ? fmtMs(rec.latency_ms) : "—"}</div>
                <MetricTooltip text={latencyDescription} />
              </div>
              <div className={`run-stat has-metric-tooltip ${metricRangeClass("turn_count", turnValue)}`}>
                <div className="run-stat-k">Turns</div>
                <div className="run-stat-v">{String(out.turns ?? "—")}</div>
                <MetricTooltip text={getMetricDescription("turn_count", turnValue)} />
              </div>
              <div className={`run-stat has-metric-tooltip ${metricRangeClass("tool_call_count", toolCallCount)}`}>
                <div className="run-stat-k">Tool Calls</div>
                <div className="run-stat-v">{toolCallCount}</div>
                <MetricTooltip text={getMetricDescription("tool_call_count", toolCallCount)} />
              </div>
              <div className="run-stat has-metric-tooltip">
                <div className="run-stat-k">Avg Score</div>
                <div className="run-stat-v">{score != null ? score.toFixed(2) : "—"}</div>
                <MetricTooltip text={avgScoreDescription} />
              </div>
            </div>
            <div className="run-metric-browser">
              <div className="run-metric-options" role="tablist" aria-label="Metric categories">
                {TRACE_METRIC_GROUPS.map((group) => {
                  const count = group.metrics.filter((name) => scoreForMetric(rec, name) != null).length;
                  const active = group.id === selectedMetricGroup.id;
                  return (
                    <button
                      key={group.id}
                      type="button"
                      role="tab"
                      aria-selected={active}
                      className={`run-metric-option ${active ? "active" : ""}`}
                      onClick={() => setMetricGroup(group.id)}
                    >
                      <span>{group.label}</span>
                      <strong>{count}</strong>
                    </button>
                  );
                })}
              </div>
              <div className="run-evals" role="tabpanel" aria-label={selectedMetricGroup.label}>
                {visibleScores.length ? (
                  visibleScores.map(([name, value]) => (
                    <div key={name} className={`eval-score has-metric-tooltip ${metricRangeClass(name, value)}`}>
                      <span className="eval-score-name">{name}</span>
                      <span className="eval-score-value">{value.toFixed(2)}</span>
                      <MetricTooltip text={getMetricDescription(name, value)} />
                    </div>
                  ))
                ) : (
                  <p className="muted run-metric-empty">This sample has no {selectedMetricGroup.label} metrics</p>
                )}
              </div>
            </div>
          </div>
          <div className="sample-brief">
            <CollapsibleBrief label="TASK" text={instruction} />
            <CollapsibleBrief label="AGENT ANSWER" text={String(out.final_answer ?? "—")} />
          </div>
          <div className="card trace-card">
            <div className="run-title section-title">
              <div className="run-title-main">Trace</div>
            </div>
            {loading ? <p className="muted">Loading trace…</p> : null}
            {!loading && spanError ? <p className="muted">Failed to load trace: {spanError}</p> : null}
            {!loading && spans && spans.length > 0 ? <SpanTree spans={spans} /> : null}
            {!loading && !spanError && spans && spans.length === 0 ? <ToolFallback out={out} /> : null}
            {!loading && !spanError && spans === null && !traceId ? (
              <p className="muted">No trace_id</p>
            ) : null}
            {!loading && !spanError && spans === null && traceId && !projectName ? (
              <p className="muted">Missing project_name; unable to load trace</p>
            ) : null}
          </div>
        </div>
      ) : null}
    </div>
  );
}

interface Props {
  records: ExperimentRecord[];
  benchmarkName: string | null;
  projectName?: string;
  emptyMessage?: string;
  activeSample: number;
  onActiveSampleChange: (index: number) => void;
  onGoTask: () => void;
  onGoEval: () => void;
}

export function TracePanel({
  records,
  benchmarkName,
  projectName,
  emptyMessage,
  activeSample,
  onActiveSampleChange,
  onGoTask,
  onGoEval,
}: Props) {
  const vpRef = useRef<HTMLDivElement>(null);
  const stackRef = useRef<HTMLDivElement>(null);
  const scrollReportedSampleRef = useRef(activeSample);
  const [openIndex, setOpenIndex] = useState<number | null>(null);
  const [braceH, setBraceH] = useState(64);

  const syncBraces = useCallback(() => {
    const stack = stackRef.current;
    if (!stack) return;
    setBraceH(Math.max(64, Math.ceil(stack.getBoundingClientRect().height)));
  }, []);

  useEffect(() => {
    const stack = stackRef.current;
    if (!stack || typeof ResizeObserver === "undefined") return;
    const ro = new ResizeObserver(syncBraces);
    ro.observe(stack);
    syncBraces();
    return () => ro.disconnect();
  }, [records.length, openIndex, syncBraces]);

  useEffect(() => {
    setOpenIndex(null);
    scrollReportedSampleRef.current = 0;
    vpRef.current?.scrollTo({ top: 0 });
  }, [records]);

  useEffect(() => {
    const vp = vpRef.current;
    if (!vp) return;
    const onScroll = () => {
      const cards = [...vp.querySelectorAll<HTMLElement>(".scard-card")];
      if (!cards.length) return;
      const ref = vp.getBoundingClientRect().top + 100;
      let best = 0;
      let bd = Infinity;
      cards.forEach((c, i) => {
        const d = Math.abs(c.getBoundingClientRect().top - ref);
        if (d < bd) {
          bd = d;
          best = i;
        }
      });
      scrollReportedSampleRef.current = best;
      onActiveSampleChange(best);
    };
    vp.addEventListener("scroll", onScroll, { passive: true });
    return () => vp.removeEventListener("scroll", onScroll);
  }, [records.length, onActiveSampleChange]);

  useEffect(() => {
    const vp = vpRef.current;
    if (!vp) return;
    const card = vp.querySelectorAll<HTMLElement>(".scard-card")[activeSample];
    if (!card) return;
    if (scrollReportedSampleRef.current === activeSample) return;
    // Keep content vertically centered when it does not overflow; do not force scrollTo.
    if (vp.scrollHeight <= vp.clientHeight + 2) {
      vp.scrollTop = 0;
      return;
    }
    const top = card.offsetTop - 12;
    if (Math.abs(vp.scrollTop - top) > 40) {
      vp.scrollTo({ top, behavior: "smooth" });
    }
  }, [activeSample]);

  if (!records.length) {
    return (
      <article className="panel trace wide">
        <div className="pane-empty" id="trace-empty">
          <p className="muted">{emptyMessage ?? "← Select a benchmark in Task"}</p>
        </div>
      </article>
    );
  }

  const allScores = records
    .flatMap((r) => (r.annotations ?? []).map((a) => a.score))
    .filter((x): x is number => typeof x === "number");
  const avg = allScores.length ? (allScores.reduce((s, x) => s + x, 0) / allScores.length).toFixed(2) : "—";
  const braceStyle = { height: `${braceH}px` };

  return (
    <article className="panel trace wide">
      <div className="vpager" id="trace-vpager" ref={vpRef}>
        <div className="tlink">
          <BraceBig side="left" l1="Task" l2={benchmarkName ?? ""} onClick={onGoTask} style={braceStyle} />
          <div className="sstack" ref={stackRef}>
            {records.map((rec, i) => (
              <SampleCard
                key={rec.trace_id ?? rec.id ?? i}
                rec={rec}
                index={i}
                total={records.length}
                projectName={projectName}
                open={openIndex === i}
                onToggle={() => {
                  const next = openIndex === i ? null : i;
                  setOpenIndex(next);
                  requestAnimationFrame(syncBraces);
                }}
              />
            ))}
          </div>
          <BraceBig side="right" l1="Eval" l2={`avg ${avg}`} onClick={onGoEval} style={braceStyle} />
        </div>
      </div>
    </article>
  );
}
