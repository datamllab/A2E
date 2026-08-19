import { ROOT_CONTEXT, trace, type Context } from "@opentelemetry/api";
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

const DEFAULT_SPAN_ATTRIBUTE_COUNT_LIMIT = 10_000;

/** Follow OTel precedence while matching A2E's shared OpenInference default. */
export function resolveSpanAttributeCountLimit(
  env: PiMonitorEnvironment = process.env,
): number {
  for (const key of ["OTEL_SPAN_ATTRIBUTE_COUNT_LIMIT", "OTEL_ATTRIBUTE_COUNT_LIMIT"] as const) {
    const value = env[key];
    if (value === undefined || value.trim() === "") continue;
    const parsed = Number(value);
    if (Number.isSafeInteger(parsed) && parsed > 0) return parsed;
  }
  return DEFAULT_SPAN_ATTRIBUTE_COUNT_LIMIT;
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

export function extractParentContext(env: PiMonitorEnvironment): Context | undefined {
  const traceparent = env.TRACEPARENT;
  if (!traceparent) return undefined;
  // W3C traceparent: "00-{trace_id(32)}-{span_id(16)}-{flags(2)}"
  const match = /^([0-9a-f]{2})-([0-9a-f]{32})-([0-9a-f]{16})-([0-9a-f]{2})$/i.exec(traceparent);
  if (!match) return undefined;
  const traceId = match[2]!;
  const spanId = match[3]!;
  const flags = match[4]!;
  try {
    const spanContext = {
      traceId,
      spanId,
      traceFlags: Number.parseInt(flags, 16),
      isRemote: true,
    };
    return trace.setSpanContext(ROOT_CONTEXT, spanContext);
  } catch {
    return undefined;
  }
}

export function createA2EPiMonitor(env: PiMonitorEnvironment = process.env): PiTraceMonitor {
  const config = resolveRuntimeConfig(env);
  const parentContext = extractParentContext(env);
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
      "service.version": "openinference-instrumentation-pi/0.1.0",
    }),
    // OTel defaults to 128 attributes per span, which long coding-agent
    // conversations exceed. Match A2E's shared OpenInference provider while
    // preserving the standard OTel environment-variable overrides.
    spanLimits: { attributeCountLimit: resolveSpanAttributeCountLimit(env) },
    spanProcessors: [processor],
  });
  const tracer = provider.getTracer("openinference-instrumentation-pi", "0.1.0");
  return new PiTraceMonitor(tracer, {
    captureContent: config.captureContent,
    maxAttributeLength: config.maxAttributeLength,
    ...(parentContext ? { parentContext } : {}),
    lifecycle: {
      forceFlush: () => provider.forceFlush(),
      shutdown: () => provider.shutdown(),
    },
  });
}
