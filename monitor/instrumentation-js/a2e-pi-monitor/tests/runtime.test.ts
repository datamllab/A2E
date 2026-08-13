import assert from "node:assert/strict";
import { createServer } from "node:http";
import { describe, it } from "node:test";
import { trace } from "@opentelemetry/api";

import {
  createA2EPiMonitor,
  extractParentContext,
  normalizeTraceEndpoint,
  parseHeaders,
  resolveRuntimeConfig,
} from "../src/runtime.js";

describe("Pi monitor runtime configuration", () => {
  it("normalizes A2E base and full trace endpoints", () => {
    assert.equal(normalizeTraceEndpoint("http://localhost:6006"), "http://localhost:6006/v1/traces");
    assert.equal(
      normalizeTraceEndpoint("http://localhost:6006/v1/traces/"),
      "http://localhost:6006/v1/traces",
    );
  });

  it("honors A2E configuration and authentication precedence", () => {
    const config = resolveRuntimeConfig({
      A2E_COLLECTOR_ENDPOINT: "https://collector.example/a2e",
      A2E_PROJECT_NAME: "pi-eval",
      A2E_CLIENT_HEADERS: "x-team=agent%20eval",
      A2E_API_KEY: "secret",
      A2E_PI_CAPTURE_CONTENT: "false",
      A2E_PI_MAX_ATTRIBUTE_LENGTH: "4096",
      OTEL_EXPORTER_OTLP_HEADERS: "x-base=one,authorization=old",
    });
    assert.deepEqual(config, {
      endpoint: "https://collector.example/a2e/v1/traces",
      projectName: "pi-eval",
      headers: {
        "x-base": "one",
        "x-team": "agent eval",
        authorization: "Bearer secret",
      },
      captureContent: false,
      maxAttributeLength: 4096,
    });
  });

  it("uses the signal-specific standard OTLP endpoint unchanged", () => {
    const config = resolveRuntimeConfig({
      OTEL_EXPORTER_OTLP_TRACES_ENDPOINT: "https://otel.example/custom/traces/",
    });
    assert.equal(config.endpoint, "https://otel.example/custom/traces");
  });

  it("extracts a remote W3C parent context for experiment-linked Pi spans", () => {
    const parent = extractParentContext({
      TRACEPARENT: "00-0123456789abcdef0123456789abcdef-0123456789abcdef-01",
    });
    assert.ok(parent);
    const spanContext = trace.getSpanContext(parent);
    assert.deepEqual(spanContext, {
      traceId: "0123456789abcdef0123456789abcdef",
      spanId: "0123456789abcdef",
      traceFlags: 1,
      isRemote: true,
    });
    assert.equal(extractParentContext({ TRACEPARENT: "not-a-traceparent" }), undefined);
  });

  it("parses W3C baggage-style headers defensively", () => {
    assert.deepEqual(parseHeaders("a=hello%20world, malformed, b=2"), {
      a: "hello world",
      b: "2",
    });
  });

  it("exports an OTLP protobuf payload accepted by A2E's HTTP trace route", async () => {
    let receive!: (value: { url: string; contentType: string; body: Buffer }) => void;
    const received = new Promise<{ url: string; contentType: string; body: Buffer }>((resolve) => {
      receive = resolve;
    });
    const server = createServer((request, response) => {
      const chunks: Buffer[] = [];
      request.on("data", (chunk: Buffer) => chunks.push(chunk));
      request.on("end", () => {
        receive({
          url: request.url ?? "",
          contentType: String(request.headers["content-type"] ?? ""),
          body: Buffer.concat(chunks),
        });
        response.writeHead(200, { "content-type": "application/x-protobuf" });
        response.end();
      });
    });
    await new Promise<void>((resolve, reject) => {
      server.once("error", reject);
      server.listen(0, "127.0.0.1", resolve);
    });
    const address = server.address();
    assert.ok(address && typeof address === "object");
    const monitor = createA2EPiMonitor({
      A2E_COLLECTOR_ENDPOINT: `http://127.0.0.1:${address.port}`,
      A2E_PROJECT_NAME: "pi-transport-test",
    });

    try {
      monitor.onAgentStart("/transport-test");
      monitor.onAgentEnd([]);
      await monitor.forceFlush();
      const request = await received;
      assert.equal(request.url, "/v1/traces");
      assert.match(request.contentType, /application\/x-protobuf/);
      assert.ok(request.body.length > 20, "expected a non-empty ExportTraceServiceRequest");
    } finally {
      await monitor.shutdown();
      await new Promise<void>((resolve, reject) =>
        server.close((error) => (error ? reject(error) : resolve())),
      );
    }
  });
});
