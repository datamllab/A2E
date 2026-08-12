import assert from "node:assert/strict";
import { afterEach, describe, it } from "node:test";

import {
  Agent,
  type AgentTool,
} from "@earendil-works/pi-agent-core";
import {
  fauxAssistantMessage,
  fauxProvider,
  fauxToolCall,
} from "@earendil-works/pi-ai/providers/faux";
import {
  BasicTracerProvider,
  InMemorySpanExporter,
  SimpleSpanProcessor,
} from "@opentelemetry/sdk-trace-base";
import { Type } from "typebox";

import { instrumentPiAgent } from "../src/core.js";
import { PiTraceMonitor } from "../src/monitor.js";

const providers: BasicTracerProvider[] = [];

afterEach(async () => {
  await Promise.all(providers.splice(0).map((provider) => provider.shutdown()));
});

describe("pi-agent-core integration", () => {
  it("instruments a standalone Agent through Agent.subscribe()", async () => {
    const exporter = new InMemorySpanExporter();
    const provider = new BasicTracerProvider({
      spanProcessors: [new SimpleSpanProcessor(exporter)],
    });
    providers.push(provider);
    const monitor = new PiTraceMonitor(provider.getTracer("pi-core-test"));

    const faux = fauxProvider({ api: "faux", provider: "faux" });
    faux.setResponses([
      fauxAssistantMessage(
        fauxToolCall("read", { path: "package.json" }, { id: "core-read-1" }),
        { stopReason: "toolUse" },
      ),
      fauxAssistantMessage("The package name is a2e-pi-monitor."),
    ]);

    const ReadParameters = Type.Object({ path: Type.String() });
    const readTool: AgentTool<typeof ReadParameters, { path: string }> = {
      name: "read",
      label: "Read",
      description: "Read a test file",
      parameters: ReadParameters,
      async execute(_toolCallId, params) {
        return {
          content: [{ type: "text", text: '{"name":"a2e-pi-monitor"}' }],
          details: { path: params.path },
        };
      },
    };

    let payloadHookCalls = 0;
    let responseHookCalls = 0;
    const originalOnPayload: NonNullable<Agent["onPayload"]> = () => {
      payloadHookCalls += 1;
      return undefined;
    };
    const originalOnResponse: NonNullable<Agent["onResponse"]> = () => {
      responseHookCalls += 1;
    };
    const fauxStream = faux.provider.streamSimple;
    const agent = new Agent({
      initialState: {
        systemPrompt: "You are a read-only test agent.",
        model: faux.getModel(),
        thinkingLevel: "off",
        tools: [readTool],
      },
      streamFn: async (model, context, options) => {
        await options?.onPayload?.(
          { model: model.id, messages: context.messages, tools: context.tools },
          model,
        );
        return fauxStream(model, context, options);
      },
      getApiKey: () => "test-only",
      onPayload: originalOnPayload,
      onResponse: originalOnResponse,
    });
    const instrumentation = instrumentPiAgent(agent, {
      cwd: "/core-workspace",
      monitor,
    });

    try {
      await agent.prompt("Read package.json and report its package name.");
    } finally {
      instrumentation.dispose();
    }

    assert.equal(faux.state.callCount, 2);
    assert.equal(payloadHookCalls, 2);
    assert.equal(responseHookCalls, 2);
    assert.equal(agent.onPayload, originalOnPayload);
    assert.equal(agent.onResponse, originalOnResponse);
    const spans = exporter.getFinishedSpans();
    const agentSpan = spans.find(
      (span) => span.attributes["openinference.span.kind"] === "AGENT",
    );
    const llmSpans = spans.filter(
      (span) => span.attributes["openinference.span.kind"] === "LLM",
    );
    const toolSpan = spans.find(
      (span) => span.attributes["openinference.span.kind"] === "TOOL",
    );

    assert.equal(spans.length, 4);
    assert.ok(agentSpan);
    assert.equal(llmSpans.length, 2);
    assert.ok(toolSpan);
    assert.match(String(agentSpan.attributes["input.value"]), /package\.json/);
    assert.equal(agentSpan.attributes["metadata.cwd"], "/core-workspace");
    assert.equal(llmSpans[0]?.attributes["llm.model_name"], "faux-1");
    assert.match(
      String(llmSpans[0]?.attributes["llm.invocation_parameters"]),
      /faux-1/,
    );
    assert.equal(llmSpans[0]?.attributes["llm.input_messages.0.message.role"], "system");
    assert.equal(llmSpans[0]?.attributes["llm.input_messages.1.message.role"], "user");
    assert.equal(toolSpan.attributes["tool.id"], "core-read-1");
    assert.equal(toolSpan.attributes["tool.name"], "read");
    assert.match(String(toolSpan.attributes["output.value"]), /a2e-pi-monitor/);
    assert.equal(toolSpan.parentSpanContext?.spanId, agentSpan.spanContext().spanId);
    for (const llmSpan of llmSpans) {
      assert.equal(llmSpan.parentSpanContext?.spanId, agentSpan.spanContext().spanId);
      assert.equal(llmSpan.spanContext().traceId, agentSpan.spanContext().traceId);
    }
  });
});
