import { useCallback, useEffect, useRef, useState } from "react";
import type { ExperimentRecord } from "../api/types";
import { annotationAverage, formatMetricValue, formatScore } from "../utils/eval";
import { getMetricDescription, metricRangeClass } from "../utils/metricDescriptions";
import { MetricTooltip } from "./MetricTooltip";

type SubMetric = [string, number | null];

interface FishboneNode {
  id: string;
  node: string;
  metric: string;
  score: number | null;
  sub?: SubMetric[];
  tooltipMetric?: string | null;
  description?: string;
}

function SubFishbone({ parentNode, subMetrics }: { parentNode: string; subMetrics: SubMetric[] }) {
  return (
    <div className="sub-fishbone-inner">
      <div className="submetric-panel">
        <div className="submetric-head">
          <div className="sub-spine-cap">{parentNode}</div>
          <div className="submetric-title">
            <span>Expanded diagnostics</span>
            <strong>{parentNode} metrics</strong>
          </div>
        </div>
        <div className="submetric-grid">
          {subMetrics.map(([name, score], i) => {
            const description = getMetricDescription(name, score);
            const rangeClass = metricRangeClass(name, score);
            return (
              <div
                key={name}
                className={`submetric-card has-metric-tooltip ${rangeClass}`}
              >
                <div className="submetric-index">{String(i + 1).padStart(2, "0")}</div>
                <div className="submetric-main">
                  <span>{name}</span>
                  <strong>{formatMetricValue(name, score)}</strong>
                </div>
                <MetricTooltip text={description} />
              </div>
            );
          })}
        </div>
      </div>
    </div>
  );
}

export function FishboneCard({ records, overall }: { records: ExperimentRecord[]; overall: number | null }) {
  const cardRef = useRef<HTMLDivElement>(null);
  const [openId, setOpenId] = useState<string | null>(null);

  const planSubMetrics: SubMetric[] = [
    ["plan_grade", annotationAverage(records, "plan_grade")],
    ["plan_goal_alignment", annotationAverage(records, "plan_goal_alignment")],
    ["plan_completeness", annotationAverage(records, "plan_completeness")],
    ["plan_constraint_adherence", annotationAverage(records, "plan_constraint_adherence")],
    ["reasoning_coherence", annotationAverage(records, "reasoning_coherence")],
    ["plan_hallucination", annotationAverage(records, "plan_hallucination")],
  ];
  const toolSubMetrics: SubMetric[] = [
    ["tool_hallucination", annotationAverage(records, "tool_hallucination")],
    ["tool_invocation", annotationAverage(records, "tool_invocation")],
    ["self_correction_rate", annotationAverage(records, "self_correction_rate")],
    ["tool_call_count", annotationAverage(records, "tool_call_count")],
  ];
  const finalSubMetrics: SubMetric[] = [
    ["correctness", annotationAverage(records, "correctness")],
    ["instruction_following", annotationAverage(records, "instruction_following")],
    ["llm_judge", annotationAverage(records, "llm_judge")],
    ["task_succeeded", annotationAverage(records, "task_succeeded")],
    ["execution_completion", annotationAverage(records, "execution_completion")],
    ["error_absence", annotationAverage(records, "error_absence")],
  ];

  const finalResultDescription = [
    "- Meaning: Structural final result node on the fishbone spine.",
    "- Calculation: Shows the benchmark-level overall score, which is the average of the first available correctness-style metric.",
    "- Expanded metrics: correctness, instruction_following, llm_judge, task_succeeded, execution_completion, and error_absence.",
  ].join("\n");

  const nodes: FishboneNode[] = [
    { id: "plan", node: "Plan", metric: "plan_grade", score: annotationAverage(records, "plan_grade"), sub: planSubMetrics },
    { id: "memory", node: "Memory", metric: "hallucination", score: annotationAverage(records, "hallucination") },
    { id: "skill", node: "Skill", metric: "conciseness", score: annotationAverage(records, "conciseness") },
    { id: "tool", node: "Tool", metric: "tool_recall", score: annotationAverage(records, "tool_recall"), sub: toolSubMetrics },
    { id: "final", node: "Final_Result", metric: "final_result", score: overall, sub: finalSubMetrics, tooltipMetric: null, description: finalResultDescription },
  ];

  const expandables = nodes.filter((n): n is FishboneNode & { sub: SubMetric[] } => Boolean(n.sub?.length));

  const drawConnector = useCallback((id: string) => {
    const card = cardRef.current;
    if (!card) return;
    const item = card.querySelector<HTMLElement>(`.fish-item[data-expand-id="${id}"]`);
    const fishNode = item?.querySelector<HTMLElement>(".fish-node");
    const wrap = card.querySelector<HTMLElement>(`.sub-fishbone-wrap[data-expand-id="${id}"]`);
    const svg = card.querySelector<SVGSVGElement>(`.sub-connector[data-expand-id="${id}"]`);
    const path = svg?.querySelector<SVGPathElement>(".sub-connector-path");
    const cap = wrap?.querySelector<HTMLElement>(".sub-spine-cap");
    if (!item || !fishNode || !wrap || !svg || !path || !cap) return;

    const cr = card.getBoundingClientRect();
    const ir = item.getBoundingClientRect();
    const nr = fishNode.getBoundingClientRect();
    const pr = cap.getBoundingClientRect();
    const isLower = item.classList.contains("lower");
    const nx = nr.left + nr.width / 2 - cr.left;
    const ny = (isLower ? ir.bottom : nr.bottom) - cr.top;
    const sx = pr.left + pr.width / 2 - cr.left;
    const sy = pr.top + pr.height / 2 - cr.top;
    svg.setAttribute("width", String(cr.width));
    svg.setAttribute("height", String(card.scrollHeight));
    const dir = sx < nx ? -1 : 1;
    const r = Math.max(0, Math.min(12, Math.abs(sx - nx) / 2, Math.abs(sy - ny) / 2));
    path.setAttribute("d", `M ${nx} ${ny} L ${nx} ${sy - r} Q ${nx} ${sy} ${nx + dir * r} ${sy} L ${sx} ${sy}`);
  }, []);

  const redrawAll = useCallback(() => {
    if (openId) drawConnector(openId);
  }, [openId, drawConnector]);

  useEffect(() => {
    if (!openId) return;
    requestAnimationFrame(() => requestAnimationFrame(redrawAll));
    window.addEventListener("resize", redrawAll);
    return () => window.removeEventListener("resize", redrawAll);
  }, [openId, redrawAll]);

  const toggle = (id: string) => {
    setOpenId((cur) => (cur === id ? null : id));
  };

  return (
    <div className="card eval-fishbone-card" ref={cardRef}>
      <p className="card-label">DIAGNOSIS</p>
      <div className="fishbone">
        <div className="fish-end fish-head">HEAD</div>
        <div className="fish-end fish-tail">TAIL</div>
        {nodes.map((n, i) => {
          const expandable = Boolean(n.sub?.length);
          const isOpen = openId === n.id;
          const tooltipMetric = n.tooltipMetric === undefined ? n.metric : n.tooltipMetric;
          const description = n.description ?? (tooltipMetric ? getMetricDescription(tooltipMetric, n.score) : null);
          const rangeClass = tooltipMetric ? metricRangeClass(tooltipMetric, n.score) : "";
          return (
            <div
              key={n.id}
              data-expand-id={expandable ? n.id : undefined}
              className={`fish-item ${i % 2 ? "lower" : "upper"}${expandable ? " fish-item-expandable" : ""}${isOpen ? " open" : ""}`}
            >
              <div className={`fish-branch ${description ? "has-metric-tooltip" : ""} ${rangeClass}`}>
                <span>{n.metric}</span>
                <strong>{formatScore(n.score)}</strong>
                {description ? <MetricTooltip text={description} /> : null}
              </div>
              <div
                className="fish-node"
                role={expandable ? "button" : undefined}
                tabIndex={expandable ? 0 : undefined}
                aria-expanded={expandable ? isOpen : undefined}
                onClick={expandable ? () => toggle(n.id) : undefined}
                onKeyDown={
                  expandable
                    ? (e) => {
                        if (e.key === "Enter" || e.key === " ") {
                          e.preventDefault();
                          toggle(n.id);
                        }
                      }
                    : undefined
                }
              >
                <span>{String(i + 1).padStart(2, "0")}</span>
                {n.node}
                {expandable ? <i className="fish-expand-caret">▸</i> : null}
              </div>
            </div>
          );
        })}
      </div>
      {expandables.map((n) => {
        const isOpen = openId === n.id;
        return (
          <svg
            key={`connector-${n.id}`}
            data-expand-id={n.id}
            className={`sub-connector${isOpen ? " open" : ""}`}
          >
            <path className="sub-connector-path" />
          </svg>
        );
      })}
      {expandables.map((n) => {
        const isOpen = openId === n.id;
        return (
          <div
            key={`sub-${n.id}`}
            data-expand-id={n.id}
            className={`sub-fishbone-wrap${isOpen ? " open" : ""}`}
            onTransitionEnd={(e) => {
              if (e.propertyName === "grid-template-rows" && isOpen) drawConnector(n.id);
            }}
          >
            <SubFishbone parentNode={n.node} subMetrics={n.sub} />
          </div>
        );
      })}
    </div>
  );
}
