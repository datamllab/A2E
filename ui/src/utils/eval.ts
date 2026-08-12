import type { AgentInfo, ExperimentRecord, ExperimentSummary } from "../api/types";
import { benchExperiments, normKey, type Benchmark } from "../data/benchmarks";
import { dbAgentFromExperiment } from "./dbIdentity";

export function agentsForExperiments(experiments: ExperimentSummary[]): AgentInfo[] {
  const byId = new Map<string, AgentInfo>();
  for (const experiment of experiments) {
    const agent = dbAgentFromExperiment(experiment);
    if (agent && !byId.has(agent.id)) byId.set(agent.id, agent);
  }
  return [...byId.values()];
}

export function experimentsForAgent(
  experiments: ExperimentSummary[],
  agent: AgentInfo | null,
): ExperimentSummary[] {
  if (!agent) return experiments;
  return experiments.filter((experiment) => dbAgentFromExperiment(experiment)?.id === agent.id);
}

export function newestExperimentsFirst(experiments: ExperimentSummary[]): ExperimentSummary[] {
  return [...experiments].sort((a, b) => {
    const createdAt = String(b.created_at ?? "").localeCompare(String(a.created_at ?? ""));
    return createdAt || String(b.id).localeCompare(String(a.id));
  });
}

export function hasEvaluationResults(records: ExperimentRecord[]): boolean {
  return records.some((record) =>
    (record.annotations ?? []).some(
      (annotation) =>
        (typeof annotation.score === "number" && Number.isFinite(annotation.score)) ||
        (typeof annotation.label === "string" && annotation.label.trim().length > 0),
    ),
  );
}

export function agentTokens(agent: AgentInfo): string[] {
  return [agent.id, agent.label, ...(agent.aliases ?? [])].map(normKey).filter(Boolean);
}

export function findAgentExperiment(
  experiments: ExperimentSummary[],
  agent: AgentInfo,
): ExperimentSummary | undefined {
  if (agent.id === "claude-agent-sdk") return experiments[0];
  const tokens = agentTokens(agent);
  return experiments.find((e) => {
    const haystack = normKey(`${e.project_name ?? ""} ${e.dataset_name ?? ""}`);
    return tokens.some((t) => haystack.includes(t));
  });
}

export function benchDefaultSelection(
  b: Benchmark,
  experiments: ExperimentSummary[],
): { b: Benchmark; exp: ExperimentSummary; agent: AgentInfo | null } | null {
  const exps = benchExperiments(b, experiments);
  if (!exps.length) return null;
  for (const exp of exps) {
    const agent = dbAgentFromExperiment(exp);
    if (agent) return { b, exp, agent };
  }
  return { b, exp: exps[0], agent: null };
}

export function defaultSelection(
  experiments: ExperimentSummary[],
  benchmarks: Benchmark[],
): { b: Benchmark; exp: ExperimentSummary; agent: AgentInfo | null } | null {
  for (const b of benchmarks) {
    const sel = benchDefaultSelection(b, experiments);
    if (sel) return sel;
  }
  return null;
}

export function sampleScore(rec: ExperimentRecord): number | null {
  const xs = (rec.annotations ?? []).map((a) => a.score).filter((x): x is number => typeof x === "number");
  return xs.length ? xs.reduce((s, x) => s + x, 0) / xs.length : null;
}

export function annotationAverage(records: ExperimentRecord[], name: string): number | null {
  const target = name.toLowerCase();
  const xs = records
    .map((r) => (r.annotations ?? []).find((a) => String(a.name).toLowerCase() === target)?.score)
    .filter((x): x is number => typeof x === "number");
  return xs.length ? xs.reduce((s, x) => s + x, 0) / xs.length : null;
}

export function annotationSum(records: ExperimentRecord[], name: string): number | null {
  const target = name.toLowerCase();
  const xs = records
    .map((r) => (r.annotations ?? []).find((a) => String(a.name).toLowerCase() === target)?.score)
    .filter((x): x is number => typeof x === "number");
  return xs.length ? xs.reduce((s, x) => s + x, 0) : null;
}

function numericValue(value: unknown): number | null {
  if (typeof value === "number" && Number.isFinite(value)) return value;
  if (typeof value === "string" && value.trim()) {
    const parsed = Number(value);
    return Number.isFinite(parsed) ? parsed : null;
  }
  return null;
}

function firstNumericField(source: Record<string, unknown> | undefined, names: string[]): number | null {
  if (!source) return null;
  for (const name of names) {
    const value = numericValue(source[name]);
    if (value !== null) return value;
  }
  return null;
}

function recordCost(rec: ExperimentRecord): number | null {
  const names = ["cost", "total_cost", "cost_usd", "total_cost_usd", "totalCost", "costUsd", "totalCostUsd"];
  const fromRecord = firstNumericField(rec as unknown as Record<string, unknown>, names);
  if (fromRecord !== null) return fromRecord;
  const fromOutput = firstNumericField(rec.output, names);
  if (fromOutput !== null) return fromOutput;
  const fromMetadata = firstNumericField(rec.metadata, names);
  if (fromMetadata !== null) return fromMetadata;

  for (const name of names) {
    const annotation = (rec.annotations ?? []).find((a) => String(a.name).toLowerCase() === name.toLowerCase());
    const value = numericValue(annotation?.score);
    if (value !== null) return value;
  }
  return null;
}

export function totalCost(records: ExperimentRecord[]): number | null {
  const xs = records.map(recordCost).filter((x): x is number => typeof x === "number");
  return xs.length ? xs.reduce((s, x) => s + x, 0) : null;
}

export function fmtMs(ms: number): string {
  if (ms < 1000) return `${Math.round(ms)}ms`;
  return `${(ms / 1000).toFixed(2)}s`;
}

export function formatScore(value: number | null | undefined): string {
  return typeof value === "number" ? value.toFixed(2) : "—";
}

export function formatMetricValue(name: string, value: number | null | undefined): string {
  if (typeof value !== "number") return "—";
  if (name === "total_token_usage" || name === "total_token" || name === "answer_cost") {
    return Math.round(value).toLocaleString("en-US");
  }
  if (name === "cost" || name === "total_cost") return formatUsd(value);
  if (name === "tool_call_count") return (Math.round(value * 10) / 10).toLocaleString("en-US");
  return value.toFixed(2);
}

export function formatUsd(value: number): string {
  if (value === 0) return "$0";
  if (Math.abs(value) < 0.000001) return "$<0.000001";
  if (Math.abs(value) < 0.01) return `$${value.toFixed(6)}`;
  if (Math.abs(value) < 1) return `$${value.toFixed(4)}`;
  return `$${value.toFixed(2)}`;
}

export function totalTokenUsage(records: ExperimentRecord[]): number | null {
  let total = 0;
  let seen = false;
  for (const r of records) {
    const prompt = typeof r.prompt_token_count === "number" ? r.prompt_token_count : 0;
    const completion = typeof r.completion_token_count === "number" ? r.completion_token_count : 0;
    if (prompt || completion) seen = true;
    total += prompt + completion;
  }
  return seen ? total : annotationAverage(records, "total_token_usage");
}
