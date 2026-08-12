import type { AgentInfo, ExperimentContext, ExperimentRecord } from "../api/types";
import { CATS, type Benchmark } from "../data/benchmarks";
import {
  annotationAverage,
  formatMetricValue,
  totalCost,
  totalTokenUsage,
} from "../utils/eval";
import { getMetricDescription, metricRangeClass } from "../utils/metricDescriptions";
import { FishboneCard } from "./FishboneCard";
import { MetricTooltip } from "./MetricTooltip";

const EFFICIENCY_METRICS = ["total_token_usage", "cost", "answer_cost", "turn_count", "elapsed_time"] as const;
const SAFETY_METRICS = [
  "hallucination",
  "privacy_leakage",
  "unauthorized_action",
  "harmful_action",
  "failure_transparency",
  "prompt_injection_resilience",
] as const;
const ACCURACY_METRICS = [
  "correctness",
  "instruction_following",
  "llm_judge",
  "task_succeeded",
  "execution_completion",
  "error_absence",
] as const;

interface Props {
  benchmark: Benchmark | null;
  records: ExperimentRecord[];
  context: ExperimentContext | null;
  agent: AgentInfo | null;
  experimentDatasetName?: string;
  projectName?: string;
  testedAgentModel?: string;
  judgeModel?: string;
  loading?: boolean;
}

function infoItem(label: string, value: string) {
  return (
    <div className="info-item">
      <div className="info-label">{label}</div>
      <div className="info-value">{value || "—"}</div>
    </div>
  );
}

export function EvalPanel({
  benchmark,
  records,
  context,
  agent,
  experimentDatasetName,
  projectName,
  testedAgentModel,
  judgeModel,
  loading = false,
}: Props) {
  if (!benchmark || !records.length) {
    return (
      <article className="panel eval">
        <div className="panel-inner" id="eval-body">
          <p className="kicker">Eval</p>
          <p className="muted">
            {loading
              ? "Loading the selected evaluation…"
              : benchmark
                ? "No samples for the selected run"
                : "← Select a benchmark in Task"}
          </p>
        </div>
      </article>
    );
  }

  const names: string[] = [];
  for (const r of records) {
    for (const a of r.annotations ?? []) {
      if (!names.includes(a.name)) names.push(a.name);
    }
  }

  const avgOf = (name: string) => {
    const target = name.toLowerCase();
    const xs = records
      .map((r) => (r.annotations ?? []).find((a) => String(a.name).toLowerCase() === target)?.score)
      .filter((x): x is number => typeof x === "number");
    return xs.length ? xs.reduce((s, x) => s + x, 0) / xs.length : null;
  };

  const avgFirst = (candidates: string[]) => {
    for (const name of candidates) {
      const value = avgOf(name);
      if (value != null) return value;
    }
    return null;
  };

  const countPasses = (name: string) => {
    const target = name.toLowerCase();
    return records.filter((r) => {
      const ann = (r.annotations ?? []).find((a) => String(a.name).toLowerCase() === target);
      if (!ann) return false;
      if (typeof ann.score === "number") return ann.score >= 0.5;
      return String(ann.label ?? "").toLowerCase() === "correct";
    }).length;
  };

  const overall = avgFirst(["correctness", "correct", "accuracy", "task_succeeded", "llm_judge"]);
  const llmPasses = countPasses("llm_judge");
  const totalCostValue = totalCost(records);
  const totalToken = totalTokenUsage(records);
  const hasScore = typeof overall === "number";
  const pct = hasScore ? Math.max(0, Math.min(100, overall * 100)) : 0;
  const good = hasScore && overall >= 0.5;
  const overallDescription = [
    "- Meaning: Benchmark-level average correctness score used as the overall result.",
    "- Calculation: Average of the first available correctness-style metric: correctness, correct, accuracy, task_succeeded, or llm_judge.",
    "- Display: 0 to 1; higher is better.",
  ].join("\n");
  const llmPassDescription = [
    "- Meaning: Number of samples that pass the LLM judge.",
    "- Calculation: Counts samples whose llm_judge score is at least 0.5; label fallback is correct.",
    "- Display: passed samples / total samples.",
  ].join("\n");
  const totalCostDescription = [
    "- Meaning: Total monetary cost across the selected benchmark.",
    "- Calculation: Sum of cost-like fields across all samples, usually in USD.",
    "- Display: Non-negative currency value.",
  ].join("\n");
  const totalTokenDescription = [
    "- Meaning: Total token usage across the selected benchmark.",
    "- Calculation: Sum of prompt and completion tokens across all samples when available; falls back to total_token_usage annotations.",
    "- Display: Non-negative token count.",
  ].join("\n");
  const domain =
    (benchmark.cat != null ? CATS[benchmark.cat] : undefined) ||
    context?.inputs?.domains?.join(", ") ||
    benchmark.name;

  const metricValue = (name: string): number | null => {
    if (name === "total_token_usage") return totalTokenUsage(records);
    if (name === "cost") return annotationAverage(records, "cost");
    return annotationAverage(records, name);
  };

  return (
    <article className="panel eval">
      <div className="panel-inner" id="eval-body">
        <p className="kicker">Eval · {benchmark.name} all-sample average</p>

        <div className="card eval-summary-card">
          <p className="card-label">SUMMARY</p>
          <div className="eval-summary-main">
            <div
              className={`ring summary-ring ${hasScore ? (good ? "good" : "bad") : ""}`}
              style={{ ["--p" as string]: pct }}
            >
              {hasScore ? overall.toFixed(2) : "—"}
            </div>
            <div className="summary-copy">
              <div className="summary-title has-metric-tooltip">
                Overall evaluator score
                <MetricTooltip text={overallDescription} />
              </div>
              <div className="summary-sub">
                {records.length} samples · average correctness
              </div>
            </div>
          </div>
          <div className="summary-stat-grid">
            <div className="metric has-metric-tooltip">
              <div className="metric-v">
                {llmPasses}/{records.length}
              </div>
              <div className="metric-k">llm pass</div>
              <MetricTooltip text={llmPassDescription} />
            </div>
            <div className="metric has-metric-tooltip">
              <div className="metric-v">{formatMetricValue("total_cost", totalCostValue)}</div>
              <div className="metric-k">total cost</div>
              <MetricTooltip text={totalCostDescription} />
            </div>
            <div className="metric has-metric-tooltip">
              <div className="metric-v">{formatMetricValue("total_token", totalToken)}</div>
              <div className="metric-k">total_token</div>
              <MetricTooltip text={totalTokenDescription} />
            </div>
          </div>
          <details className="summary-config">
            <summary>Configuration</summary>
            <div className="eval-info-card compact embedded">
              <div className="info-grid">
                {infoItem("Agent", agent?.label ?? context?.agent?.names?.join(", ") ?? "—")}
                {infoItem("Tested agent model", testedAgentModel || "—")}
                {infoItem("LLM-as-a-judge model", judgeModel || "—")}
                {infoItem("Benchmark", benchmark.name)}
                {infoItem("Dataset", context?.dataset?.name ?? experimentDatasetName ?? "—")}
                {infoItem("Project ID", projectName ?? context?.experiment?.project_name ?? "—")}
                {infoItem("Domain", domain)}
                {infoItem(
                  "Runs OK",
                  context?.runs?.ok_runs != null
                    ? `${context.runs.ok_runs}/${records.length}`
                    : "—",
                )}
              </div>
            </div>
          </details>
        </div>

        <FishboneCard records={records} overall={overall} />

        <div className="card eval-assessment-card">
          <p className="card-label">EVALUATION</p>
          <div className="assessment-tree">
            <div className="assessment-root">
              <span>Eval Tree</span>
              <strong>Metrics</strong>
            </div>
            {[
              ["Accuracy", "accuracy", ACCURACY_METRICS.map((name) => [name, metricValue(name)] as const)],
              ["Safety", "safety", SAFETY_METRICS.map((name) => [name, metricValue(name)] as const)],
              ["Efficiency", "efficiency", EFFICIENCY_METRICS.map((name) => [name, metricValue(name)] as const)],
            ].map(([label, group, metrics], i) => (
              <div key={String(label)} className={`assessment-row assessment-${group}`}>
                <div className="assessment-label">
                  <span>{String(i + 1).padStart(2, "0")}</span>
                  <strong>{String(label)}</strong>
                </div>
                <div className="assessment-values">
                  {(metrics as [string, number | null][]).map(([name, value]) => {
                    const description = getMetricDescription(name, value);
                    const rangeClass = metricRangeClass(name, value);
                    return (
                      <div
                        key={name}
                        className={`assessment-metric has-metric-tooltip ${rangeClass}`}
                      >
                        <span>{name}</span>
                        <strong>{formatMetricValue(name, value)}</strong>
                        <MetricTooltip text={description} />
                      </div>
                    );
                  })}
                </div>
              </div>
            ))}
          </div>
        </div>
      </div>
    </article>
  );
}
