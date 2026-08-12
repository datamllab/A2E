import { fetchJSON } from "./client";
import type { ExperimentContext, ExperimentRecord, ExperimentSummary } from "./types";
import { getTraceSpans } from "./spans";
import {
  dbAgentFrameworksFromMetadata,
  dbAgentNamesFromMetadata,
  dbModelNamesFromMetadata,
  dbModelNamesFromRecords,
  dbModelNamesFromSpans,
  uniqStrings,
} from "../utils/dbIdentity";

interface DatasetRow {
  id: string;
  name?: string;
  metadata?: Record<string, unknown>;
}

interface ExperimentRow {
  id: string;
  dataset_id: string;
  name?: string;
  created_at?: string;
  example_count?: number;
  successful_run_count?: number;
  failed_run_count?: number;
  project_name?: string;
  metadata?: Record<string, unknown>;
}

interface Page<T> {
  data?: T[];
  next_cursor?: string | null;
}

async function fetchPages<T>(path: string, limit: number): Promise<T[]> {
  const out: T[] = [];
  let cursor: string | null | undefined = null;
  do {
    const params = new URLSearchParams({ limit: String(limit) });
    if (cursor) params.set("cursor", cursor);
    const sep = path.includes("?") ? "&" : "?";
    const page = await fetchJSON<Page<T>>(`${path}${sep}${params.toString()}`);
    out.push(...(page.data ?? []));
    cursor = page.next_cursor;
  } while (cursor);
  return out;
}

export async function listExperiments(): Promise<ExperimentSummary[]> {
  const datasets = await fetchPages<DatasetRow>("/v1/datasets", 100);
  const out: ExperimentSummary[] = [];
  for (const ds of datasets) {
    const experiments = await fetchPages<ExperimentRow>(
      `/v1/datasets/${encodeURIComponent(ds.id)}/experiments`,
      100,
    );
    for (const exp of experiments) {
      out.push({
        id: exp.id,
        dataset_id: exp.dataset_id,
        name: exp.name,
        dataset_name: ds.name ?? ds.id,
        created_at: exp.created_at,
        example_count: exp.example_count,
        successful_run_count: exp.successful_run_count,
        failed_run_count: exp.failed_run_count,
        project_name: exp.project_name,
        metadata: exp.metadata,
        dataset_metadata: ds.metadata,
      });
    }
  }
  out.sort((a, b) => String(b.created_at ?? "").localeCompare(String(a.created_at ?? "")));
  return out;
}

export async function getExperimentJson(experimentId: string): Promise<ExperimentRecord[]> {
  const data = await fetchJSON<ExperimentRecord[] | { data?: ExperimentRecord[] }>(
    `/v1/experiments/${encodeURIComponent(experimentId)}/json`,
  );
  if (Array.isArray(data)) return data;
  return data.data ?? [];
}

export async function getLatestExperiment(): Promise<{
  experiment: ExperimentSummary | null;
  records: ExperimentRecord[];
}> {
  const experiments = await listExperiments();
  if (!experiments.length) return { experiment: null, records: [] };
  const experiment = experiments[0];
  const records = await getExperimentJson(experiment.id);
  return { experiment, records };
}

interface ExperimentDetail {
  id: string;
  dataset_id: string;
  name?: string;
  project_name?: string;
  created_at?: string;
  metadata?: Record<string, unknown>;
  successful_run_count?: number;
  failed_run_count?: number;
  example_count?: number;
}

interface DatasetDetail {
  name?: string;
  description?: string;
}

function uniq(xs: (string | undefined | null)[]): string[] {
  const out: string[] = [];
  for (const x of xs) {
    if (!x) continue;
    if (!out.includes(x)) out.push(x);
  }
  return out;
}

async function observedModelsFromTraceSpans(projectName: string | undefined, records: ExperimentRecord[]): Promise<string[]> {
  if (!projectName) return [];
  const traceIds = uniq(records.map((r) => r.trace_id)).slice(0, 6);
  if (!traceIds.length) return [];
  const spanSets = await Promise.all(
    traceIds.map((traceId) => getTraceSpans(projectName, traceId).catch(() => [])),
  );
  return dbModelNamesFromSpans(spanSets.flat());
}

export async function getExperimentContext(
  experimentId: string,
  records: ExperimentRecord[],
): Promise<ExperimentContext> {
  try {
    const expRes = await fetchJSON<{ data: ExperimentDetail }>(
      `/v1/experiments/${encodeURIComponent(experimentId)}`,
    );
    const exp = expRes.data;
    const dsRes = await fetchJSON<{ data: DatasetDetail }>(
      `/v1/datasets/${encodeURIComponent(exp.dataset_id)}`,
    );
    const domains: string[] = [];
    const expectedActions: string[] = [];
    const expectedOutputs: string[] = [];
    for (const rec of records) {
      const meta = rec.metadata ?? {};
      if (meta.domain) domains.push(String(meta.domain));
      const ref = rec.reference_output ?? {};
      if (Array.isArray(ref.expected_actions)) {
        for (const a of ref.expected_actions) {
          expectedActions.push(typeof a === "string" ? a : String((a as { name?: string }).name ?? a));
        }
      }
      if (Array.isArray(ref.expected_outputs)) {
        expectedOutputs.push(...ref.expected_outputs.map(String));
      }
    }
    const okRuns = records.filter((r) => {
      const status = String(r.output?.status ?? "").toLowerCase();
      return !r.error && status !== "error" && status !== "failed";
    }).length;
    const latencies = records.map((r) => r.latency_ms).filter((x): x is number => typeof x === "number");
    const metadataModels = dbModelNamesFromMetadata(exp.metadata);
    const recordModels = dbModelNamesFromRecords(records);
    const spanModels =
      metadataModels.length || recordModels.length
        ? []
        : await observedModelsFromTraceSpans(exp.project_name, records);
    const modelNames = uniqStrings([...metadataModels, ...recordModels, ...spanModels]);
    return {
      available: true,
      experiment: {
        id: exp.id,
        name: exp.name,
        project_name: exp.project_name,
        created_at: exp.created_at,
        metadata: exp.metadata,
      },
      dataset: { name: dsRes.data.name, description: dsRes.data.description },
      runs: {
        runs: (exp.successful_run_count ?? 0) + (exp.failed_run_count ?? 0),
        ok_runs: okRuns,
        avg_latency_ms: latencies.length
          ? latencies.reduce((s, x) => s + x, 0) / latencies.length
          : undefined,
      },
      inputs: {
        domains: uniq(domains),
        expected_actions: uniq(expectedActions),
        expected_outputs: uniq(expectedOutputs),
      },
      agent: {
        names: dbAgentNamesFromMetadata(exp.metadata),
        frameworks: dbAgentFrameworksFromMetadata(exp.metadata),
      },
      models: modelNames.length
        ? {
            task: modelNames.map((name) => ({ name })),
            observed: modelNames,
          }
        : undefined,
    };
  } catch {
    return { available: false };
  }
}
