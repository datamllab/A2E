import type { AgentInfo, ExperimentContext, ExperimentRecord, ExperimentSummary, SpanNode } from "../api/types";

const AGENT_KEYS = ["agent", "agent_name", "agent_id", "agent_framework", "framework", "sdk"] as const;
const FRAMEWORK_KEYS = ["agent_framework", "framework", "sdk"] as const;
const MODEL_KEYS = [
  "model",
  "model_name",
  "llm_model",
  "llm_model_name",
  "task_model",
  "answer_model",
  "completion_model",
  "chat_model",
] as const;
const TESTED_AGENT_MODEL_KEYS = [
  "agent_model",
  "agent_model_name",
  "tested_agent_model",
  "tested_model",
  "target_model",
  "subject_model",
  "task_model",
  "answer_model",
  "completion_model",
  "chat_model",
  "model",
  "model_name",
] as const;
const JUDGE_MODEL_KEYS = [
  "judge_model",
  "judge_model_name",
  "llm_judge_model",
  "llm_judge_model_name",
  "llm_as_judge_model",
  "llm_as_a_judge_model",
  "evaluator_model",
  "evaluator_model_name",
  "eval_model",
  "eval_model_name",
  "metric_model",
  "scorer_model",
  "llm_model",
  "llm_model_name",
] as const;
const PROVIDER_KEYS = ["provider", "model_provider", "llm_provider"] as const;

function normId(value: string): string {
  return value.toLowerCase().replace(/[^a-z0-9]+/g, "-").replace(/^-+|-+$/g, "");
}

function cleanString(value: unknown): string {
  if (typeof value === "string") return value.trim();
  if (typeof value === "number" || typeof value === "boolean") return String(value);
  return "";
}

export function uniqStrings(values: (string | undefined | null)[]): string[] {
  const out: string[] = [];
  for (const value of values) {
    const label = cleanString(value);
    if (label && !out.includes(label)) out.push(label);
  }
  return out;
}

function collectMetadataStrings(meta: Record<string, unknown> | undefined, keys: readonly string[]): string[] {
  if (!meta) return [];
  const values: string[] = [];
  for (const key of keys) values.push(cleanString(meta[key]));
  return uniqStrings(values);
}

function collectRecordModelStrings(records: ExperimentRecord[]): string[] {
  const values: string[] = [];
  for (const rec of records) {
    values.push(...collectMetadataStrings(rec.metadata, MODEL_KEYS));
    values.push(...collectMetadataStrings(rec.output, MODEL_KEYS));
  }
  return uniqStrings(values);
}

function attrString(attrs: Record<string, unknown> | undefined, keys: readonly string[]): string {
  if (!attrs) return "";
  for (const key of keys) {
    const direct = cleanString(attrs[key]);
    if (direct) return direct;
    const dotted = cleanString(attrs[`llm.${key}`]);
    if (dotted) return dotted;
  }
  return "";
}

export function dbAgentNamesFromMetadata(meta: Record<string, unknown> | undefined): string[] {
  return collectMetadataStrings(meta, AGENT_KEYS);
}

export function dbAgentFrameworksFromMetadata(meta: Record<string, unknown> | undefined): string[] {
  return collectMetadataStrings(meta, FRAMEWORK_KEYS);
}

export function dbAgentFromExperiment(exp: ExperimentSummary): AgentInfo | null {
  const names = dbAgentNamesFromMetadata(exp.metadata);
  const label = names[0];
  if (!label) return null;
  return {
    id: normId(label) || `experiment-${exp.id}`,
    label,
    aliases: names.slice(1),
  };
}

export function dbModelNamesFromMetadata(meta: Record<string, unknown> | undefined): string[] {
  return collectMetadataStrings(meta, MODEL_KEYS);
}

export function dbModelNamesFromRecords(records: ExperimentRecord[]): string[] {
  return collectRecordModelStrings(records);
}

export function dbModelNamesFromSpans(spans: SpanNode[]): string[] {
  const values: string[] = [];
  for (const span of spans) {
    if (String(span.span_kind ?? "").toUpperCase() !== "LLM") continue;
    const model = attrString(span.attributes, MODEL_KEYS);
    const provider = attrString(span.attributes, PROVIDER_KEYS);
    values.push(model ? (provider && !model.includes(provider) ? `${provider}/${model}` : model) : "");
  }
  return uniqStrings(values);
}

export function dbModelNamesFromContext(context: ExperimentContext | null): string[] {
  if (!context) return [];
  const taskModels = context.models?.task?.map((m) =>
    m.name ? (m.provider && !m.name.includes(m.provider) ? `${m.provider}/${m.name}` : m.name) : "",
  );
  return uniqStrings([...(taskModels ?? []), ...(context.models?.observed ?? [])]);
}

function collectRecordModelStringsByKeys(records: ExperimentRecord[], keys: readonly string[]): string[] {
  const values: string[] = [];
  for (const rec of records) {
    values.push(...collectMetadataStrings(rec.metadata, keys));
    values.push(...collectMetadataStrings(rec.output, keys));
  }
  return uniqStrings(values);
}

export function dbModelNamesForSelection(
  exp: ExperimentSummary | null,
  context: ExperimentContext | null,
  records: ExperimentRecord[],
): string[] {
  return uniqStrings([
    ...(exp ? dbModelNamesFromMetadata(exp.metadata) : []),
    ...dbModelNamesFromContext(context),
    ...dbModelNamesFromRecords(records),
  ]);
}

export function dbTestedAgentModelNamesForSelection(
  exp: ExperimentSummary | null,
  context: ExperimentContext | null,
  records: ExperimentRecord[],
): string[] {
  return uniqStrings([
    ...(exp ? collectMetadataStrings(exp.metadata, TESTED_AGENT_MODEL_KEYS) : []),
    ...collectMetadataStrings(context?.experiment?.metadata, TESTED_AGENT_MODEL_KEYS),
    ...collectRecordModelStringsByKeys(records, TESTED_AGENT_MODEL_KEYS),
  ]);
}

export function dbJudgeModelNamesForSelection(
  exp: ExperimentSummary | null,
  context: ExperimentContext | null,
  records: ExperimentRecord[],
): string[] {
  return uniqStrings([
    ...(exp ? collectMetadataStrings(exp.metadata, JUDGE_MODEL_KEYS) : []),
    ...collectMetadataStrings(context?.experiment?.metadata, JUDGE_MODEL_KEYS),
    ...collectRecordModelStringsByKeys(records, JUDGE_MODEL_KEYS),
  ]);
}
