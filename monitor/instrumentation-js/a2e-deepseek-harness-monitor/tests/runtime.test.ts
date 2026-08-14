import assert from "node:assert/strict";
import { createServer } from "node:http";
import { describe, it } from "node:test";

import {
  createA2EDeepSeekMonitor,
  extractParentContext,
  normalizeTraceEndpoint,
  parseHeaders,
  resolveRuntimeConfig,
} from "../src/runtime.js";
import type { HarnessSession } from "../src/types.js";

describe("DeepSeek monitor runtime", () => {
  it("normalizes A2E endpoints, headers, privacy, and trace parents", () => {
    assert.equal(normalizeTraceEndpoint("http://localhost:6006/"), "http://localhost:6006/v1/traces");
    assert.deepEqual(parseHeaders("x-one=hello%20world,bad,x-two=2"), {
      "x-one": "hello world",
      "x-two": "2",
    });
    const config = resolveRuntimeConfig({
      A2E_COLLECTOR_ENDPOINT: "https://collector.example/a2e",
      A2E_PROJECT_NAME: "deepseek-test",
      A2E_API_KEY: "token",
      A2E_DEEPSEEK_CAPTURE_CONTENT: "false",
      A2E_DEEPSEEK_MAX_ATTRIBUTE_LENGTH: "4096",
    });
    assert.deepEqual(config, {
      endpoint: "https://collector.example/a2e/v1/traces",
      projectName: "deepseek-test",
      headers: { authorization: "Bearer token" },
      captureContent: false,
      maxAttributeLength: 4096,
    });
    assert.ok(extractParentContext({
      TRACEPARENT: "00-4bf92f3577b34da6a3ce929d0e0e4736-00f067aa0ba902b7-01",
    }));
    assert.equal(extractParentContext({ TRACEPARENT: "invalid" }), undefined);
  });

  it("exports OTLP protobuf spans to A2E's trace endpoint", async () => {
    let path = "";
    let bodyLength = 0;
    const server = createServer((request, response) => {
      path = request.url ?? "";
      request.on("data", (chunk: Buffer) => bodyLength += chunk.length);
      request.on("end", () => {
        response.writeHead(200, { "content-type": "application/json" });
        response.end("{}");
      });
    });
    await new Promise<void>((resolve) => server.listen(0, "127.0.0.1", resolve));
    const address = server.address();
    assert.ok(address && typeof address === "object");
    const monitor = createA2EDeepSeekMonitor({
      A2E_COLLECTOR_ENDPOINT: `http://127.0.0.1:${address.port}`,
      A2E_PROJECT_NAME: "deepseek-transport-test",
    });
    const session: HarnessSession = {
      id: "transport-session",
      header: {},
      deriveMessages: () => [],
    };
    monitor.onSessionCreated(session);
    monitor.onSessionEvent(session, {
      type: "turn/start",
      seq: 0,
      time: Date.now(),
      data: { turn: 1 },
    });
    monitor.onSessionEvent(session, {
      type: "turn/end",
      seq: 1,
      time: Date.now() + 1,
      data: { turn: 1, reason: { kind: "completed" } },
    });
    await monitor.shutdown();
    await new Promise<void>((resolve, reject) => server.close((error) => error ? reject(error) : resolve()));
    assert.equal(path, "/v1/traces");
    assert.ok(bodyLength > 0);
  });
});
