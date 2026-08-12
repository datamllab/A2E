import { apiBase, fetchJSON } from "./client";
import type { SpanNode } from "./types";

interface ApiSpan {
  id?: string;
  span_id?: string;
  name?: string;
  context?: { trace_id?: string; span_id?: string };
  span_kind?: string;
  parent_id?: string | null;
  parent_span_id?: string | null;
  start_time?: string;
  end_time?: string;
  attributes?: Record<string, unknown>;
  events?: unknown[];
  status_code?: string;
  status_message?: string;
}

function normalizeSpan(raw: ApiSpan): SpanNode {
  return {
    span_id: raw.context?.span_id ?? raw.span_id ?? raw.id ?? "",
    parent_id: raw.parent_id ?? raw.parent_span_id ?? null,
    name: raw.name ?? "",
    span_kind: raw.span_kind,
    start_time: raw.start_time ?? "",
    end_time: raw.end_time ?? "",
    attributes: raw.attributes,
    events: raw.events,
    status_code: raw.status_code,
    status_message: raw.status_message,
  };
}

export async function getTraceSpans(project: string, traceId: string): Promise<SpanNode[]> {
  const [proxySpans, v1Spans] = await Promise.all([
    getTraceSpansFromProxy(project, traceId),
    getTraceSpansFromV1(project, traceId).catch(() => []),
  ]);
  return mergeTraceSpans(proxySpans, v1Spans);
}

function mergeTraceSpans(...sets: SpanNode[][]): SpanNode[] {
  const byId = new Map<string, SpanNode>();
  for (const spans of sets) {
    for (const span of spans) {
      const id = span.span_id;
      if (!id) continue;
      const prev = byId.get(id);
      if (!prev || JSON.stringify(span.attributes ?? {}).length > JSON.stringify(prev.attributes ?? {}).length) {
        byId.set(id, span);
      }
    }
  }
  return [...byId.values()].sort((a, b) => +new Date(a.start_time) - +new Date(b.start_time));
}

async function getTraceSpansFromProxy(project: string, traceId: string): Promise<SpanNode[]> {
  const p = encodeURIComponent(project);
  const t = encodeURIComponent(traceId);
  const url = `${apiBase()}/api/trace?project=${p}&trace_id=${t}`;
  try {
    const res = await fetch(url, { headers: { accept: "application/json" } });
    if (!res.ok) return [];
    const data = (await res.json()) as { spans?: ApiSpan[] };
    return (data.spans ?? []).map(normalizeSpan).filter((s) => s.span_id);
  } catch {
    return [];
  }
}

async function getTraceSpansFromV1(project: string, traceId: string): Promise<SpanNode[]> {
  const p = encodeURIComponent(project);
  const spans: ApiSpan[] = [];
  let cursor: string | null | undefined = null;
  do {
    const params = new URLSearchParams({ trace_id: traceId, limit: "1000" });
    if (cursor) params.set("cursor", cursor);
    const data = await fetchJSON<{ data?: ApiSpan[]; next_cursor?: string | null }>(
      `/v1/projects/${p}/spans?${params.toString()}`,
    );
    spans.push(...(data.data ?? []));
    cursor = data.next_cursor;
  } while (cursor);
  return spans.map(normalizeSpan).filter((s) => s.span_id);
}
