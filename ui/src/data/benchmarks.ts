export const CATS = ["Coding", "Conversational", "Research", "Computer use"] as const;
export const CAPS = ["Skill", "Memory", "Tool"] as const;

export type BenchDiff = "found" | "med" | "hard" | "front";

export interface Benchmark {
  name: string;
  cat?: number;
  year: string;
  date?: string;
  diff: BenchDiff;
  dim?: number;
  key?: string;
  experimentIds?: string[];
}

// Presentation metadata only. Benchmark cards are never created from this list;
// the current database's experiment metadata is the sole source of card names/counts.
const BENCHMARK_PRESENTATION_PRESETS: Benchmark[] = [
  { name: "HumanEval", cat: 0, year: "2021", diff: "found", key: "humaneval" },
  { name: "SWE-bench Lite", cat: 0, year: "2024", diff: "hard", dim: 2, key: "swe-bench-lite" },
  { name: "SWE-bench Verified", cat: 0, year: "2024", diff: "hard", dim: 2, key: "swe-bench-verified" },
  { name: "SWE-bench Pro", cat: 0, year: "2025", diff: "front", dim: 2, key: "swe-bench-pro" },
  { name: "SkillsBench", year: "2026", date: "2026-02-13", diff: "front", dim: 0 },
  { name: "SkillCraft", year: "2026", date: "2026-02-28", diff: "front", dim: 0 },
  { name: "SWE-Skills-Bench", year: "2026", date: "2026-03-16", diff: "front", dim: 0 },
  { name: "SkillTester", year: "2026", date: "2026-03-28", diff: "front", dim: 0 },
  { name: "SkillSafetyBench", year: "2026", date: "2026-05-12", diff: "front", dim: 0 },
  { name: "LoCoMo", year: "2024", date: "2024-02-27", diff: "hard", dim: 1 },
  { name: "LongMemEval", year: "2024", date: "2024-10-14", diff: "hard", dim: 1 },
  { name: "MemoryAgentBench", year: "2025", date: "2025-07-07", diff: "front", dim: 1 },
  { name: "EvoMemBench", year: "2026", date: "2026-05-18", diff: "front", dim: 1 },
  { name: "MemGym", year: "2026", date: "2026-05-20", diff: "front", dim: 1 },
  { name: "τ-bench", cat: 1, year: "2024", diff: "hard", dim: 2, key: "tau-bench" },
  { name: "τ²-bench", cat: 1, year: "2025", diff: "found", dim: 2, key: "tau2" },
  { name: "τ³-bench", cat: 1, year: "2026", diff: "found", dim: 2, key: "tau3" },
  { name: "GAIA", cat: 2, year: "2023", diff: "med" },
  { name: "GPQA", cat: 2, year: "2023", diff: "hard" },
  { name: "AssistantBench", cat: 2, year: "2024", diff: "hard", dim: 2 },
  { name: "BrowseComp", cat: 2, year: "2025", diff: "front", dim: 2 },
  { name: "Humanity's Last Exam", cat: 2, year: "2025", diff: "front" },
  { name: "WebShop", cat: 3, year: "2022", diff: "med", dim: 2 },
  { name: "WebArena", cat: 3, year: "2023", diff: "hard", dim: 2 },
  { name: "OSWorld", cat: 3, year: "2024", diff: "hard", dim: 2 },
  { name: "AndroidWorld", cat: 3, year: "2024", diff: "med", dim: 2 },
  { name: "TheAgentCompany", cat: 3, year: "2024", diff: "front" },
];

export function normKey(s: string): string {
  return String(s || "")
    .toLowerCase()
    .normalize("NFKD")
    .replace(/τ/g, "tau")
    .replace(/[^a-z0-9]/g, "");
}

export function benchKey(b: Benchmark): string {
  return b.key || b.name;
}

const BENCHMARK_RELEASE_YEARS: Readonly<Record<string, string>> = {
  ...Object.fromEntries(
    BENCHMARK_PRESENTATION_PRESETS.map((benchmark) => [
      normKey(benchKey(benchmark)),
      benchmark.year,
    ]),
  ),
  mmlu: "2020",
  gsm8k: "2021",
  persistbench: "2026",
  trajectbench: "2025",
  gdpval: "2025",
  mmlupro: "2024",
  arcchallenge: "2018",
  truthfulqa: "2021",
  bbh: "2022",
  agieval: "2023",
  commonsenseqa: "2018",
  hellaswag: "2019",
  openbookqa: "2018",
  math: "2021",
  // HumanEval-test is the original HumanEval test split released with the 2021 paper.
  humanevaltest: "2021",
  // Benchmark/task release years; these intentionally need not equal later paper years.
  theagentcompany: "2024",
  tau3bench: "2026",
  terminalbench2: "2025",
};

const BENCHMARK_RELEASE_YEAR_PREFIXES = Object.keys(BENCHMARK_RELEASE_YEARS).sort(
  (a, b) => b.length - a.length,
);

function benchmarkReleaseYear(label: string): string | undefined {
  const key = normKey(label);
  const candidates = key.startsWith("qa") ? [key, key.slice(2)] : [key];
  for (const candidate of candidates) {
    const exact = BENCHMARK_RELEASE_YEARS[candidate];
    if (exact) return exact;
    const benchmarkPrefix = BENCHMARK_RELEASE_YEAR_PREFIXES.find((prefix) =>
      candidate.startsWith(prefix),
    );
    if (benchmarkPrefix) return BENCHMARK_RELEASE_YEARS[benchmarkPrefix];
  }
  return undefined;
}

import type { ExperimentSummary } from "../api/types";

const BENCHMARK_META_KEYS = [
  "benchmark",
  "benchmark_name",
  "bench",
  "dataset",
  "dataset_name",
  "task",
  "task_name",
  "suite",
  "harness",
  "harness_name",
  "eval_harness",
  "evaluation_harness",
] as const;

function dbLabel(value: unknown): string {
  return String(value ?? "").trim();
}

function displayBenchmarkName(label: string): string {
  return label.replace(/^a2e[-_\s]+/i, "").trim() || label;
}

function firstString(values: unknown[]): string {
  for (const value of values) {
    if (typeof value === "string" && value.trim()) return value;
    if (typeof value === "number") return String(value);
  }
  return "";
}

function experimentBenchmarkLabel(exp: ExperimentSummary): string {
  const meta = exp.metadata ?? {};
  const datasetMeta = exp.dataset_metadata ?? {};
  const metadataLabel = firstString([
    ...BENCHMARK_META_KEYS.map((key) => meta[key]),
    ...BENCHMARK_META_KEYS.map((key) => datasetMeta[key]),
  ]);
  return (
    dbLabel(metadataLabel) ||
    dbLabel(exp.dataset_name) ||
    dbLabel(exp.name) ||
    dbLabel(exp.project_name) ||
    `Experiment ${exp.id.slice(0, 8)}`
  );
}

function databaseBenchmarkYear(exp: ExperimentSummary): string | undefined {
  const metaYear = firstString([
    exp.metadata?.benchmark_year,
    exp.metadata?.year,
    exp.dataset_metadata?.benchmark_year,
    exp.dataset_metadata?.year,
  ]);
  if (/^\d{4}$/.test(metaYear)) return metaYear;
  return undefined;
}

function experimentCreatedYear(exp: ExperimentSummary): string {
  const createdYear = String(exp.created_at ?? "").match(/\b(20\d{2})\b/)?.[1];
  return createdYear ?? new Date().getFullYear().toString();
}

function inferCategory(label: string): number {
  const key = normKey(label);
  if (/persistbench|locomo|longmemeval|memoryagentbench|evomembench|memgym/.test(key)) return 1;
  if (/taubench|tau2|tau3|chat|dialog|retail|airline|customer/.test(key)) return 1;
  if (/gdpval|terminalbench|osworld|androidworld|webarena|webshop|computer|browser|shop/.test(key)) return 3;
  if (/^qa(gpqa|mmlupro|arcchallenge|openbookqa)$/.test(key)) return 2;
  if (
    /trajectbench|agieval|bbh|commonsenseqa|gsm8k|hellaswag|math|mmlu|truthfulqa|gaia|browse|assistant|exam|research|qa/.test(
      key,
    )
  ) {
    return 1;
  }
  if (/humaneval|swe|code|mbpp|repo/.test(key)) return 0;
  return 1;
}

function inferDimension(label: string): number | undefined {
  const key = normKey(label);
  if (/persistbench|locomo|longmemeval|memoryagentbench|evomembench|memgym/.test(key)) return 1;
  if (
    /taubench|tau2|tau3|trajectbench|terminalbench|gdpval|swebench|assistantbench|browsecomp|webshop|webarena|osworld|androidworld/.test(
      key,
    )
  ) {
    return 2;
  }
  return undefined;
}

function inferDiff(label: string): BenchDiff {
  const key = normKey(label);
  if (/tau2|tau3|tauii|tauiii|humaneval/.test(key)) return "found";
  if (/frontier|front/.test(key)) return "front";
  if (/swebenchpro|terminalbench|gdpval/.test(key)) return "hard";
  if (/hard|verified|gpqa|browse|assistant|longmem|loco|webarena|osworld/.test(key)) {
    return "hard";
  }
  if (
    /medium|med|lite|gaia|webshop|android|tau|mmlu|gsm8k|agieval|arcchallenge|bbh|commonsenseqa|hellaswag|openbookqa|truthfulqa|persistbench|trajectbench|math/.test(
      key,
    )
  ) {
    return "med";
  }
  if (/found|basic/.test(key)) return "found";
  return "med";
}

function presentationPresetFor(label: string): Benchmark | undefined {
  const key = normKey(label);
  if (!key) return undefined;
  return BENCHMARK_PRESENTATION_PRESETS.find((b) => {
    const bench = normKey(benchKey(b));
    const name = normKey(b.name);
    return key === bench || key === name;
  });
}

function pushUnique(xs: string[], value: string) {
  if (!xs.includes(value)) xs.push(value);
}

export function benchmarksFromExperiments(experiments: ExperimentSummary[]): Benchmark[] {
  const byKey = new Map<string, Benchmark>();
  for (const exp of experiments) {
    const rawLabel = experimentBenchmarkLabel(exp);
    const displayLabel = displayBenchmarkName(rawLabel);
    const known = presentationPresetFor(displayLabel);
    // Preserve the database value as the identity: two distinct database labels
    // must remain two distinct cards, even if punctuation/casing is similar.
    const groupKey = rawLabel;
    if (!groupKey) continue;
    const prev = byKey.get(groupKey);
    if (prev) {
      pushUnique((prev.experimentIds ??= []), exp.id);
      continue;
    }
    const year =
      databaseBenchmarkYear(exp) ??
      known?.year ??
      benchmarkReleaseYear(displayLabel) ??
      experimentCreatedYear(exp);
    byKey.set(groupKey, {
      name: displayLabel,
      cat: known?.cat ?? inferCategory(displayLabel),
      year,
      date: known?.date,
      diff: known?.diff ?? inferDiff(displayLabel),
      dim: known?.dim ?? inferDimension(displayLabel),
      key: groupKey,
      experimentIds: [exp.id],
    });
  }
  return [...byKey.values()].sort((a, b) => {
    const yearCmp = String(a.year).localeCompare(String(b.year));
    return yearCmp || a.name.localeCompare(b.name);
  });
}

export function benchExperiments(b: Benchmark, experiments: ExperimentSummary[]): ExperimentSummary[] {
  if (b.experimentIds?.length) {
    const ids = new Set(b.experimentIds);
    return experiments.filter((e) => ids.has(e.id));
  }
  const key = normKey(benchKey(b));
  if (!key) return [];
  return experiments.filter((e) => {
    const metaAgent = String(e.metadata?.agent ?? "");
    const haystack = normKey(`${e.name || ""} ${e.dataset_name || ""} ${e.project_name || ""} ${metaAgent}`);
    return haystack.includes(key);
  });
}
