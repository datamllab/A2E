import assert from "node:assert/strict";
import { afterEach, describe, it } from "node:test";

import { SpanStatusCode } from "@opentelemetry/api";
import {
  BasicTracerProvider,
  InMemorySpanExporter,
  SimpleSpanProcessor,
} from "@opentelemetry/sdk-trace-base";

import { DeepSeekTraceMonitor, _test } from "../src/monitor.js";
import type { HarnessEvent, HarnessMessage, HarnessSession } from "../src/types.js";

const providers: BasicTracerProvider[] = [];

afterEach(async () => {
  await Promise.all(providers.splice(0).map((provider) => provider.shutdown()));
});

function fixture(options: { captureContent?: boolean } = {}) {
  const exporter = new InMemorySpanExporter();
  const provider = new BasicTracerProvider({
    spanProcessors: [new SimpleSpanProcessor(exporter)],
  });
  providers.push(provider);
  const monitor = new DeepSeekTraceMonitor(provider.getTracer("test"), options);
  let messages: HarnessMessage[] = [];
  const session: HarnessSession = {
    id: "session-test",
    header: { createdAt: 1_700_000_000_000, cwd: "/workspace" },
    deriveMessages: () => [...messages],
  };
  let seq = 0;
  let time = 1_700_000_000_000;
  const emit = (type: string, data: Record<string, unknown>): void => {
    if (type === "user/message") messages.push(data as HarnessMessage);
    if (type === "assistant/message" && data.message) messages.push(data.message as HarnessMessage);
    if (type === "tool/result" && data.message) messages.push(data.message as HarnessMessage);
    const event: HarnessEvent = { type, data, seq: seq++, time: time += 10 };
    monitor.onSessionEvent(session, event);
  };
  monitor.onSessionCreated(session);
  return { emit, exporter, monitor, session };
}

describe("DeepSeekTraceMonitor", () => {
  it("maps a complete Harness turn to one AGENT tree with LLM and TOOL children", () => {
    const { emit, exporter } = fixture();
    const user = {
      id: "user-1",
      role: "user",
      source: { kind: "user" },
      content: [{ type: "text", text: "Read package.json" }],
    };
    emit("turn/start", { turn: 1 });
    emit("user/message", user);
    emit("step/start", { turn: 1, step: 1 });
    emit("request/header", {
      reason: "initial",
      header: {
        config: { provider: "deepseek-official", model: "deepseek-v4-flash", maxTokens: 4096 },
        system: "You are a coding agent.",
        tools: [{ name: "read", description: "Read a file", parameters: { type: "object" } }],
      },
    });
    const firstAssistant = {
      id: "assistant-1",
      role: "assistant",
      source: { kind: "model", provider: "deepseek-official", model: "deepseek-v4-flash" },
      content: [
        { type: "reasoning", text: "I should inspect the file." },
        { type: "tool-call", id: "call-1", name: "read", arguments: "{\"path\":\"package.json\"}" },
      ],
    };
    emit("assistant/message", {
      turn: 1,
      step: 1,
      message: firstAssistant,
      usage: {
        inputTokens: 10,
        cacheReadTokens: 3,
        cacheWriteTokens: 2,
        outputTokens: 7,
        reasoningTokens: 4,
      },
    });
    emit("tool/call", {
      turn: 1,
      step: 1,
      callId: "call-1",
      name: "read",
      arguments: "{\"path\":\"package.json\"}",
    });
    emit("tool/result", {
      turn: 1,
      step: 1,
      message: {
        id: "tool-1",
        role: "user",
        source: { kind: "tool", callId: "call-1" },
        content: [{
          type: "tool-result",
          toolCallId: "call-1",
          isError: false,
          content: [{ type: "text", text: "{\"name\":\"demo\"}" }],
        }],
      },
    });
    emit("step/end", { turn: 1, step: 1 });
    emit("step/start", { turn: 1, step: 2 });
    emit("assistant/message", {
      turn: 1,
      step: 2,
      message: {
        id: "assistant-2",
        role: "assistant",
        source: { kind: "model", provider: "deepseek-official", model: "deepseek-v4-flash" },
        content: [{ type: "text", text: "The package name is demo." }],
      },
      usage: { inputTokens: 20, outputTokens: 6 },
    });
    emit("step/end", { turn: 1, step: 2 });
    emit("turn/end", { turn: 1, reason: { kind: "completed" } });

    const spans = exporter.getFinishedSpans();
    assert.equal(spans.length, 4);
    const agent = spans.find((span) => span.attributes["openinference.span.kind"] === "AGENT");
    const llms = spans.filter((span) => span.attributes["openinference.span.kind"] === "LLM");
    const tool = spans.find((span) => span.attributes["openinference.span.kind"] === "TOOL");
    assert.ok(agent);
    assert.equal(llms.length, 2);
    assert.ok(tool);
    for (const child of [...llms, tool]) {
      assert.equal(child.spanContext().traceId, agent.spanContext().traceId);
      assert.equal(child.parentSpanContext?.spanId, agent.spanContext().spanId);
    }
    assert.equal(agent.status.code, SpanStatusCode.OK);
    assert.equal(agent.attributes["metadata.cwd"], "/workspace");
    assert.match(String(agent.attributes["output.value"]), /package name is demo/i);
    assert.equal(llms[0]?.attributes["llm.model_name"], "deepseek-v4-flash");
    assert.equal(llms[0]?.attributes["llm.provider"], "deepseek-official");
    assert.equal(llms[0]?.attributes["llm.token_count.prompt"], 15);
    assert.equal(llms[0]?.attributes["llm.token_count.completion"], 7);
    assert.equal(llms[0]?.attributes["llm.token_count.total"], 22);
    assert.equal(llms[0]?.attributes["llm.token_count.prompt_details.cache_read"], 3);
    assert.equal(llms[0]?.attributes["llm.token_count.completion_details.reasoning"], 4);
    assert.equal(llms[0]?.attributes["llm.input_messages.0.message.role"], "system");
    assert.match(String(llms[1]?.attributes["input.value"]), /tool-result/);
    assert.match(String(llms[1]?.attributes["input.value"]), /demo/);
    assert.equal(
      llms[0]?.attributes[
        "llm.output_messages.0.message.tool_calls.0.tool_call.function.arguments_json"
      ],
      "{\"path\":\"package.json\"}",
    );
    assert.equal(tool.attributes["tool.name"], "read");
    assert.equal(tool.attributes["tool.id"], "call-1");
    assert.match(String(tool.attributes["output.value"]), /demo/);
  });

  it("records tool and turn failures without leaving unfinished spans", () => {
    const { emit, exporter } = fixture();
    emit("turn/start", { turn: 2 });
    emit("step/start", { turn: 2, step: 1 });
    emit("tool/call", {
      turn: 2,
      step: 1,
      callId: "bad-call",
      name: "bash",
      arguments: "{\"command\":\"false\"}",
    });
    emit("tool/result", {
      turn: 2,
      step: 1,
      message: {
        role: "user",
        source: { kind: "tool", callId: "bad-call" },
        content: [{
          type: "tool-result",
          toolCallId: "bad-call",
          isError: true,
          content: [{ type: "text", text: "exit code 1" }],
        }],
      },
      error: { name: "ToolError", code: "NON_ZERO_EXIT" },
    });
    emit("step/end", { turn: 2, step: 1 });
    emit("turn/end", {
      turn: 2,
      reason: { kind: "error", error: { code: "UNKNOWN", message: "task failed" } },
    });

    const spans = exporter.getFinishedSpans();
    const agent = spans.find((span) => span.attributes["openinference.span.kind"] === "AGENT");
    const llm = spans.find((span) => span.attributes["openinference.span.kind"] === "LLM");
    const tool = spans.find((span) => span.attributes["openinference.span.kind"] === "TOOL");
    assert.equal(agent?.status.code, SpanStatusCode.ERROR);
    assert.equal(agent?.status.message, "task failed");
    assert.equal(llm?.status.code, SpanStatusCode.ERROR);
    assert.equal(tool?.status.code, SpanStatusCode.ERROR);
    assert.match(tool?.status.message ?? "", /exit code 1/);
  });

  it("pairs provider tool calls whose persisted call id is empty", () => {
    const { emit, exporter, monitor, session } = fixture();
    emit("turn/start", { turn: 1 });
    emit("step/start", { turn: 1, step: 1 });

    const toolCall: HarnessEvent = {
      type: "tool/call",
      seq: 41,
      time: 1_700_000_000_100,
      data: {
        turn: 1,
        step: 1,
        callId: "",
        name: "bash",
        arguments: "{\"command\":\"pwd\"}",
      },
    };
    monitor.onSessionEvent(session, toolCall);
    monitor.onSessionEvent(session, {
      type: "tool/result",
      seq: 42,
      time: 1_700_000_000_120,
      sourceEventSeqs: [41],
      data: {
        turn: 1,
        step: 1,
        message: {
          role: "user",
          source: { kind: "tool", callId: "" },
          content: [{
            type: "tool-result",
            toolCallId: "",
            isError: false,
            content: [{ type: "text", text: "/workspace" }],
          }],
        },
      },
    });
    emit("step/end", { turn: 1, step: 1 });
    emit("turn/end", { turn: 1, reason: { kind: "completed" } });

    const tool = exporter.getFinishedSpans().find(
      (span) => span.attributes["openinference.span.kind"] === "TOOL",
    );
    assert.ok(tool);
    assert.equal(tool.attributes["tool.id"], "dsh-event-41");
    assert.equal(tool.attributes["tool.id.synthetic"], true);
    assert.equal(tool.attributes["tool.name"], "bash");
    assert.equal(tool.status.code, SpanStatusCode.OK);
    assert.match(String(tool.attributes["output.value"]), /workspace/);
  });

  it("keeps operational metadata while omitting captured content", () => {
    const { emit, exporter } = fixture({ captureContent: false });
    const secret = "sensitive-secret-value";
    emit("turn/start", { turn: 1 });
    emit("user/message", {
      role: "user",
      source: { kind: "user" },
      content: [{ type: "text", text: secret }],
    });
    emit("step/start", { turn: 1, step: 1 });
    emit("request/header", {
      header: {
        config: { provider: "private-provider", model: "private-model" },
        system: secret,
      },
    });
    emit("assistant/message", {
      turn: 1,
      step: 1,
      message: {
        role: "assistant",
        source: { kind: "model", provider: "private-provider", model: "private-model" },
        content: [{ type: "text", text: secret }],
      },
      usage: { inputTokens: 4, outputTokens: 2 },
    });
    emit("turn/end", { turn: 1, reason: { kind: "completed" } });

    const spans = exporter.getFinishedSpans();
    assert.doesNotMatch(JSON.stringify(spans.map((span) => span.attributes)), new RegExp(secret));
    const llm = spans.find((span) => span.attributes["openinference.span.kind"] === "LLM");
    assert.equal(llm?.attributes["llm.model_name"], "private-model");
    assert.equal(llm?.attributes["llm.token_count.total"], 6);
    for (const span of spans) {
      assert.equal(span.attributes["input.value"], undefined);
      assert.equal(span.attributes["output.value"], undefined);
    }
  });

  it("bounds circular and oversized values", () => {
    const circular: Record<string, unknown> = { value: 1 };
    circular.self = circular;
    assert.match(_test.safeStringify(circular, 10_000), /\[Circular\]/);
    const truncated = JSON.parse(_test.safeStringify({ text: "x".repeat(3_000) }, 1_024));
    assert.equal(truncated._a2e_truncated, true);
  });
});
