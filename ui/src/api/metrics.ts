import metricsCatalog from "../../../eval/metrics_catalog.json";
import type { MetricsCatalog } from "./types";

export function getMetricsCatalog(): MetricsCatalog {
  return metricsCatalog as unknown as MetricsCatalog;
}

export function catalogGroupMetrics(group: string): string[] {
  const cats = getMetricsCatalog().categories ?? {};
  for (const top of Object.values(cats)) {
    const g = top?.groups?.[group];
    if (g?.metrics) return g.metrics.map((m) => m.name);
  }
  return [];
}
