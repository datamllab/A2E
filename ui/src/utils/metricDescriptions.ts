import { getMetricsCatalog } from "../api/metrics";
import type { MetricCatalogEntry } from "../api/types";

type RangeState = "ok" | "warn" | "unknown";
type ScoreDomain = NonNullable<MetricCatalogEntry["output_contract"]>["score_domain"];

const FALLBACK_DESC: Record<string, string> = {
  total_cost: "Total monetary cost across the selected benchmark, usually in USD.",
  total_token: "Total prompt and completion tokens consumed by the selected benchmark.",
};

function metricEntries(): MetricCatalogEntry[] {
  const out: MetricCatalogEntry[] = [];
  const cats = getMetricsCatalog().categories ?? {};
  for (const category of Object.values(cats)) {
    for (const group of Object.values(category.groups ?? {})) {
      out.push(...(group.metrics ?? []));
    }
  }
  return out;
}

export function getMetricCatalogEntry(name: string): MetricCatalogEntry | null {
  const key = String(name || "").toLowerCase();
  return metricEntries().find((m) => String(m.name).toLowerCase() === key) ?? null;
}

function fmtNumber(value: number): string {
  return Number.isInteger(value) ? String(value) : String(Number(value.toFixed(4)));
}

function fmtList(values: Array<string | number>): string {
  return values.map((v) => (typeof v === "number" ? fmtNumber(v) : v)).join(", ");
}

function displayAverageRange(domain: ScoreDomain): string | null {
  if (!domain) return null;
  if (domain.kind === "discrete_enum" && domain.allowed_values?.length) {
    const min = Math.min(...domain.allowed_values);
    const max = Math.max(...domain.allowed_values);
    return "Displayed average should be " + fmtNumber(min) + " to " + fmtNumber(max) + ".";
  }
  if (domain.kind === "discrete_integer_range") {
    const min = domain.minimum ?? 0;
    const max = domain.maximum;
    return max == null
      ? "Displayed average should be >= " + fmtNumber(min) + "."
      : "Displayed average should be " + fmtNumber(min) + " to " + fmtNumber(max) + ".";
  }
  return null;
}

function scoreContractText(entry: MetricCatalogEntry | null, name: string): string {
  const key = String(name || "").toLowerCase();
  const domain = entry?.output_contract?.score_domain;
  if (domain?.kind === "discrete_enum" && domain.allowed_values?.length) {
    const average = displayAverageRange(domain);
    return "Per-sample score must be one of: " + fmtList(domain.allowed_values) + "." + (average ? " " + average : "");
  }
  if (domain?.kind === "continuous_range") {
    const min = domain.minimum ?? 0;
    const max = domain.maximum;
    return max == null ? "Score must be >= " + fmtNumber(min) + "." : "Score must be " + fmtNumber(min) + " to " + fmtNumber(max) + ".";
  }
  if (domain?.kind === "discrete_integer_range") {
    const min = domain.minimum ?? 0;
    const max = domain.maximum;
    const bound = max == null ? ">= " + fmtNumber(min) : fmtNumber(min) + " to " + fmtNumber(max);
    const average = displayAverageRange(domain);
    return "Per-sample score must be an integer-like count " + bound + "." + (average ? " " + average : "");
  }
  if (entry?.score_type === "binary" || entry?.score_type === "graded") return "Score should be 0 to 1.";
  if (entry?.score_type === "magnitude") return "Score should be a non-negative raw magnitude.";
  if (key === "total_cost" || key === "total_token") return "Displayed aggregate should be non-negative.";
  return "Score contract is not defined in eval/metrics_catalog.json.";
}

function labelContractText(entry: MetricCatalogEntry | null): string {
  const label = entry?.output_contract?.label;
  const enumLabels = label?.enum ?? label?.enum_or_pattern?.enum;
  const pattern = label?.enum_or_pattern?.pattern;
  const catalogLabels = entry?.labels;
  const labels = enumLabels?.length ? enumLabels : catalogLabels;
  if (labels?.length && pattern) return "Labels: " + labels.join(", ") + ", or pattern " + pattern + ".";
  if (labels?.length) return "Labels: " + labels.join(", ") + ".";
  if (pattern) return "Label pattern: " + pattern + ".";
  return "";
}

function positiveLabelText(entry: MetricCatalogEntry | null): string {
  const positives = entry?.output_contract?.positive_labels;
  if (positives?.length) return "Positive labels: " + positives.join(", ") + ".";
  if (entry?.positive_label) return "Positive label: " + entry.positive_label + ".";
  return "";
}

function noteText(entry: MetricCatalogEntry | null): string {
  const notes = entry?.output_contract?.notes?.filter(Boolean).slice(0, 2) ?? [];
  return notes.length ? "Contract notes: " + notes.join(" ") : "";
}

function inDisplayedRange(domain: ScoreDomain, value: number): boolean | null {
  if (!domain) return null;
  if (domain.kind === "discrete_enum" && domain.allowed_values?.length) {
    return value >= Math.min(...domain.allowed_values) && value <= Math.max(...domain.allowed_values);
  }
  if (domain.kind === "continuous_range" || domain.kind === "discrete_integer_range") {
    const min = domain.minimum;
    const max = domain.maximum;
    return (min == null || value >= min) && (max == null || value <= max);
  }
  return null;
}

export function metricRangeState(name: string, value: number | null | undefined): RangeState {
  if (typeof value !== "number" || !Number.isFinite(value)) return "unknown";
  const key = String(name || "").toLowerCase();
  const entry = getMetricCatalogEntry(name);
  const contractState = inDisplayedRange(entry?.output_contract?.score_domain, value);
  if (contractState != null) return contractState ? "ok" : "warn";
  if (entry?.score_type === "binary" || entry?.score_type === "graded") {
    return value >= 0 && value <= 1 ? "ok" : "warn";
  }
  if (entry?.score_type === "magnitude" || key === "total_cost" || key === "total_token") {
    return value >= 0 ? "ok" : "warn";
  }
  return "unknown";
}

export function metricRangeClass(name: string, value: number | null | undefined): string {
  const state = metricRangeState(name, value);
  return state === "ok" ? "range-ok" : state === "warn" ? "range-warn" : "range-unknown";
}

export function getMetricDescription(name: string, value?: number | null): string {
  const key = String(name || "").toLowerCase();
  const entry = getMetricCatalogEntry(name);
  const desc = entry?.desc || FALLBACK_DESC[key] || "Evaluator metric: " + name + ".";
  const score = scoreContractText(entry, name);
  const type = entry
    ? "Evaluator: " + (entry.kind ?? "not defined") + "; score type: " + (entry.score_type ?? "not defined") + "."
    : "Evaluator and score type are not defined in eval/metrics_catalog.json.";
  const current = typeof value === "number" && Number.isFinite(value)
    ? "Displayed value: " + fmtNumber(value) + " (" + (metricRangeState(name, value) === "warn" ? "outside expected range" : "inside expected range") + ")."
    : "";
  return [
    "- Meaning: " + desc,
    "- Score contract: " + score,
    "- Type: " + type,
    positiveLabelText(entry) ? "- " + positiveLabelText(entry) : "",
    labelContractText(entry) ? "- " + labelContractText(entry) : "",
    current ? "- " + current : "",
    noteText(entry) ? "- " + noteText(entry) : "",
  ]
    .filter(Boolean)
    .join("\n");
}
