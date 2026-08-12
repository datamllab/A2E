import { dirname, resolve } from "node:path";
import { fileURLToPath } from "node:url";

import {
  Agent,
  type AgentTool,
} from "@earendil-works/pi-agent-core";
import {
  fauxAssistantMessage,
  fauxProvider,
  fauxToolCall,
} from "@earendil-works/pi-ai/providers/faux";
import { Type } from "typebox";

import { instrumentPiAgent } from "../src/core.js";

const packageRoot = resolve(dirname(fileURLToPath(import.meta.url)), "../..");
const faux = fauxProvider({ api: "faux", provider: "faux" });
faux.setResponses([
  fauxAssistantMessage(
    fauxToolCall("read", { path: "package.json" }, { id: "core-smoke-read" }),
    { stopReason: "toolUse" },
  ),
  fauxAssistantMessage("The package name is a2e-pi-monitor."),
]);

const ReadParameters = Type.Object({ path: Type.String() });
const readTool: AgentTool<typeof ReadParameters, { path: string }> = {
  name: "read",
  label: "Read",
  description: "Read the package manifest used by this deterministic smoke test",
  parameters: ReadParameters,
  async execute(_toolCallId, params) {
    return {
      content: [{ type: "text", text: '{"name":"a2e-pi-monitor"}' }],
      details: { path: params.path },
    };
  },
};

const fauxStream = faux.provider.streamSimple;
const agent = new Agent({
  initialState: {
    systemPrompt: "You are a read-only monitor test agent.",
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
});
const tracing = instrumentPiAgent(agent, { cwd: packageRoot });

try {
  await agent.prompt("Read package.json and report its package name.");
  console.log(JSON.stringify({
    piCoreVersion: "0.84.1",
    modelCalls: faux.state.callCount,
    collector: process.env.A2E_COLLECTOR_ENDPOINT ?? "http://127.0.0.1:6006",
    project: process.env.A2E_PROJECT_NAME ?? "default",
  }, null, 2));
} finally {
  await tracing.shutdown();
}
