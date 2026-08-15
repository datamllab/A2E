import assert from "node:assert/strict";
import { afterEach, describe, it } from "node:test";

import { SpanStatusCode } from "@opentelemetry/api";
import {
  BasicTracerProvider,
  InMemorySpanExporter,
  SimpleSpanProcessor,
} from "@opentelemetry/sdk-trace-base";

import { PiTraceMonitor, _test } from "../src/monitor.js";

const providers: BasicTracerProvider[] = [];

afterEach(async () => {
  await Promise.all(providers.splice(0).map((provider) => provider.shutdown()));
});

function fixture() {
  const exporter = new InMemorySpanExporter();
  const provider = new BasicTracerProvider({
    spanProcessors: [new SimpleSpanProcessor(exporter)],
  });
  providers.push(provider);
  const monitor = new PiTraceMonitor(provider.getTracer("test"));
  return { exporter, monitor };
}

describe("PiTraceMonitor", () => {
  it("captures an agent, model call, and tool call as one OpenInference trace", () => {
    const { exporter, monitor } = fixture();
    monitor.onBeforeAgentStart({
      prompt: "List the files",
      systemPrompt: "You are a coding agent.",
    });
    monitor.onAgentStart("/workspace");
    monitor.onContext([{ role: "user", content: "List the files" }]);
    monitor.onBeforeProviderRequest({ model: "claude-test", max_tokens: 1024 });
    monitor.onProviderResponse(200);

    const assistant = {
      role: "assistant",
      provider: "anthropic",
      api: "anthropic-messages",
      model: "claude-test",
      content: [
        { type: "text", text: "I'll inspect the directory." },
        { type: "toolCall", id: "call-1", name: "bash", arguments: { command: "ls" } },
      ],
      usage: {
        input: 11,
        output: 7,
        cacheRead: 3,
        cost: { input: 0.01, output: 0.02, total: 0.03 },
      },
      stopReason: "toolUse",
    };
    monitor.onMessageStart(assistant);
    monitor.onMessageEnd(assistant);
    monitor.onToolStart({ toolCallId: "call-1", toolName: "bash", args: { command: "ls" } });
    monitor.onToolEnd({
      toolCallId: "call-1",
      toolName: "bash",
      result: { content: [{ type: "text", text: "README.md" }] },
      isError: false,
    });
    monitor.onAgentEnd([assistant]);

    const spans = exporter.getFinishedSpans();
    assert.equal(spans.length, 3);
    const agent = spans.find((span) => span.attributes["openinference.span.kind"] === "AGENT");
    const llm = spans.find((span) => span.attributes["openinference.span.kind"] === "LLM");
    const tool = spans.find((span) => span.attributes["openinference.span.kind"] === "TOOL");
    assert.ok(agent);
    assert.ok(llm);
    assert.ok(tool);

    assert.equal(llm.spanContext().traceId, agent.spanContext().traceId);
    assert.equal(tool.spanContext().traceId, agent.spanContext().traceId);
    assert.equal(llm.parentSpanContext?.spanId, agent.spanContext().spanId);
    assert.equal(tool.parentSpanContext?.spanId, agent.spanContext().spanId);

    assert.equal(llm.attributes["llm.model_name"], "claude-test");
    assert.equal(llm.attributes["llm.provider"], "anthropic");
    assert.equal(llm.attributes["llm.token_count.prompt"], 11);
    assert.equal(llm.attributes["llm.token_count.completion"], 7);
    assert.equal(llm.attributes["llm.token_count.total"], 18);
    assert.equal(llm.attributes["llm.input_messages.0.message.role"], "system");
    assert.equal(llm.attributes["llm.input_messages.1.message.role"], "user");
    assert.equal(llm.attributes["llm.output_messages.0.message.role"], "assistant");
    assert.equal(
      llm.attributes[
        "llm.output_messages.0.message.tool_calls.0.tool_call.function.arguments_json"
      ],
      '{"command":"ls"}',
    );
    assert.equal(tool.attributes["tool.id"], "call-1");
    assert.equal(tool.attributes["tool.name"], "bash");
    assert.match(String(tool.attributes["output.value"]), /README\.md/);
    assert.equal(agent.status.code, SpanStatusCode.OK);
    assert.equal(llm.status.code, SpanStatusCode.OK);
    assert.equal(tool.status.code, SpanStatusCode.OK);
  });

  it("keeps parallel tools separate and records failures", () => {
    const { exporter, monitor } = fixture();
    monitor.onAgentStart();
    monitor.onToolStart({ toolCallId: "a", toolName: "read", args: { path: "a.txt" } });
    monitor.onToolStart({ toolCallId: "b", toolName: "bash", args: { command: "false" } });
    monitor.onToolEnd({
      toolCallId: "b",
      toolName: "bash",
      result: { message: "exit code 1" },
      isError: true,
    });
    monitor.onToolEnd({
      toolCallId: "a",
      toolName: "read",
      result: { content: [{ type: "text", text: "ok" }] },
      isError: false,
    });
    monitor.onAgentEnd([]);

    const tools = exporter
      .getFinishedSpans()
      .filter((span) => span.attributes["openinference.span.kind"] === "TOOL");
    assert.equal(tools.length, 2);
    const failed = tools.find((span) => span.attributes["tool.id"] === "b");
    const passed = tools.find((span) => span.attributes["tool.id"] === "a");
    assert.equal(failed?.status.code, SpanStatusCode.ERROR);
    assert.equal(failed?.status.message, "exit code 1");
    assert.equal(passed?.status.code, SpanStatusCode.OK);
  });

  it("closes unfinished child spans when an agent ends", () => {
    const { exporter, monitor } = fixture();
    monitor.onAgentStart();
    monitor.onMessageStart({ role: "assistant", model: "test-model" });
    monitor.onToolStart({ toolCallId: "orphan", toolName: "read", args: {} });
    monitor.onAgentEnd([]);

    const spans = exporter.getFinishedSpans();
    assert.equal(spans.length, 3);
    assert.equal(
      spans.find((span) => span.name.startsWith("pi.llm"))?.status.code,
      SpanStatusCode.ERROR,
    );
    assert.equal(
      spans.find((span) => span.name.startsWith("pi.tool"))?.status.code,
      SpanStatusCode.ERROR,
    );
  });

  it("serializes circular values and bounds oversized attributes", () => {
    const circular: Record<string, unknown> = { value: 1 };
    circular.self = circular;
    assert.match(_test.safeStringify(circular, 10_000), /\[Circular\]/);
    const truncated = JSON.parse(_test.safeStringify({ text: "x".repeat(3_000) }, 1_024));
    assert.equal(truncated._a2e_truncated, true);
    assert.equal(truncated.original_length, 3_011);
  });

  it("omits prompt and tool content when content capture is disabled", () => {
    const exporter = new InMemorySpanExporter();
    const provider = new BasicTracerProvider({
      spanProcessors: [new SimpleSpanProcessor(exporter)],
    });
    providers.push(provider);
    const monitor = new PiTraceMonitor(provider.getTracer("privacy-test"), {
      captureContent: false,
    });
    const secret = "sensitive-user-content";

    monitor.onBeforeAgentStart({ prompt: secret, systemPrompt: secret });
    monitor.onAgentStart("/workspace");
    monitor.onContext([{ role: "user", content: secret }]);
    monitor.onBeforeProviderRequest({
      model: "private-model",
      messages: [{ role: "user", content: secret }],
    });
    const assistant = {
      role: "assistant",
      provider: "private-provider",
      model: "private-model",
      content: secret,
      usage: { input: 4, output: 2 },
      stopReason: "error",
      errorMessage: secret,
    };
    monitor.onMessageStart(assistant);
    monitor.onMessageEnd(assistant);
    monitor.onToolStart({
      toolCallId: "private-tool-1",
      toolName: "write",
      args: { content: secret },
    });
    monitor.onToolEnd({
      toolCallId: "private-tool-1",
      toolName: "write",
      result: { message: secret },
      isError: true,
    });
    monitor.onAgentEnd([assistant]);

    const spans = exporter.getFinishedSpans();
    assert.equal(spans.length, 3);
    assert.doesNotMatch(
      JSON.stringify(spans.map((span) => ({
        attributes: span.attributes,
        events: span.events,
        status: span.status,
      }))),
      /sensitive-user-content/,
    );
    const llm = spans.find((span) => span.attributes["openinference.span.kind"] === "LLM");
    const tool = spans.find((span) => span.attributes["openinference.span.kind"] === "TOOL");
    assert.equal(llm?.attributes["llm.model_name"], "private-model");
    assert.equal(llm?.attributes["llm.provider"], "private-provider");
    assert.equal(llm?.attributes["llm.token_count.total"], 6);
    assert.equal(llm?.attributes["llm.invocation_parameters"], undefined);
    assert.equal(tool?.attributes["tool.name"], "write");
    assert.equal(tool?.attributes["tool.parameters"], undefined);
    for (const span of spans) {
      assert.equal(span.attributes["input.value"], undefined);
      assert.equal(span.attributes["output.value"], undefined);
    }
  });
});
