import { OTLPTraceExporter } from "@opentelemetry/exporter-trace-otlp-proto";
import { resourceFromAttributes } from "@opentelemetry/resources";
import { BasicTracerProvider, BatchSpanProcessor } from "@opentelemetry/sdk-trace-base";

import { PiTraceMonitor } from "./monitor.js";

export interface PiMonitorEnvironment extends NodeJS.ProcessEnv {
  A2E_COLLECTOR_ENDPOINT?: string;
  A2E_PROJECT_NAME?: string;
  A2E_CLIENT_HEADERS?: string;
  A2E_API_KEY?: string;
  A2E_PI_CAPTURE_CONTENT?: string;
  A2E_PI_MAX_ATTRIBUTE_LENGTH?: string;
  OTEL_EXPORTER_OTLP_ENDPOINT?: string;
  OTEL_EXPORTER_OTLP_TRACES_ENDPOINT?: string;
  OTEL_EXPORTER_OTLP_HEADERS?: string;
}

function enabled(value: string | undefined, fallback: boolean): boolean {
  if (value === undefined) return fallback;
  return !["0", "false", "no", "off"].includes(value.trim().toLowerCase());
}

export function normalizeTraceEndpoint(endpoint: string): string {
  const trimmed = endpoint.trim().replace(/\/+$/, "");
  return trimmed.endsWith("/v1/traces") ? trimmed : `${trimmed}/v1/traces`;
}

export function parseHeaders(value: string | undefined): Record<string, string> {
  if (!value) return {};
  const headers: Record<string, string> = {};
  for (const item of value.split(",")) {
    const separator = item.indexOf("=");
    if (separator < 1) continue;
    const key = item.slice(0, separator).trim();
    const raw = item.slice(separator + 1).trim();
    try {
      headers[key] = decodeURIComponent(raw);
    } catch {
      headers[key] = raw;
    }
  }
  return headers;
}

export function resolveRuntimeConfig(env: PiMonitorEnvironment = process.env): {
  endpoint: string;
  projectName: string;
  headers: Record<string, string>;
  captureContent: boolean;
  maxAttributeLength: number;
} {
  const explicitTraceEndpoint = env.OTEL_EXPORTER_OTLP_TRACES_ENDPOINT;
  const baseEndpoint =
    env.A2E_COLLECTOR_ENDPOINT ?? env.OTEL_EXPORTER_OTLP_ENDPOINT ??
    "http://127.0.0.1:6006";
  const endpoint = explicitTraceEndpoint
    ? explicitTraceEndpoint.replace(/\/+$/, "")
    : normalizeTraceEndpoint(baseEndpoint);
  const headers = {
    ...parseHeaders(env.OTEL_EXPORTER_OTLP_HEADERS),
    ...parseHeaders(env.A2E_CLIENT_HEADERS),
  };
  if (env.A2E_API_KEY) headers.authorization = `Bearer ${env.A2E_API_KEY}`;
  const parsedLimit = Number(env.A2E_PI_MAX_ATTRIBUTE_LENGTH);
  return {
    endpoint,
    projectName: env.A2E_PROJECT_NAME || "default",
    headers,
    captureContent: enabled(env.A2E_PI_CAPTURE_CONTENT, true),
    maxAttributeLength:
      Number.isFinite(parsedLimit) && parsedLimit >= 1_024 ? parsedLimit : 262_144,
  };
}

export function createA2EPiMonitor(env: PiMonitorEnvironment = process.env): PiTraceMonitor {
  const config = resolveRuntimeConfig(env);
  const exporter = new OTLPTraceExporter({
    url: config.endpoint,
    headers: config.headers,
    timeoutMillis: 5_000,
    concurrencyLimit: 4,
  });
  const processor = new BatchSpanProcessor(exporter, {
    maxQueueSize: 2_048,
    maxExportBatchSize: 256,
    scheduledDelayMillis: 250,
    exportTimeoutMillis: 5_000,
  });
  const provider = new BasicTracerProvider({
    resource: resourceFromAttributes({
      "openinference.project.name": config.projectName,
      "service.name": "pi-agent",
      "service.version": "a2e-pi-monitor/0.1.0",
    }),
    spanProcessors: [processor],
  });
  const tracer = provider.getTracer("a2e-pi-monitor", "0.1.0");
  return new PiTraceMonitor(tracer, {
    captureContent: config.captureContent,
    maxAttributeLength: config.maxAttributeLength,
    lifecycle: {
      forceFlush: () => provider.forceFlush(),
      shutdown: () => provider.shutdown(),
    },
  });
}
