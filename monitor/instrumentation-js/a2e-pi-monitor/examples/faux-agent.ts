import { mkdtemp, rm } from "node:fs/promises";
import { tmpdir } from "node:os";
import { dirname, join, resolve } from "node:path";
import { fileURLToPath } from "node:url";

import {
  createAgentSession,
  DefaultResourceLoader,
  ModelRuntime,
  SessionManager,
} from "@earendil-works/pi-coding-agent";
import {
  fauxAssistantMessage,
  fauxProvider,
  fauxToolCall,
} from "@earendil-works/pi-ai/providers/faux";

const packageRoot = resolve(dirname(fileURLToPath(import.meta.url)), "../..");
const agentDir = await mkdtemp(join(tmpdir(), "a2e-pi-smoke-"));

const loader = new DefaultResourceLoader({
  cwd: packageRoot,
  agentDir,
  additionalExtensionPaths: [packageRoot],
});
await loader.reload();
const loaded = loader.getExtensions();
if (loaded.errors.length) {
  throw new Error(`Pi could not load the A2E extension: ${JSON.stringify(loaded.errors)}`);
}

const faux = fauxProvider({ api: "faux", provider: "faux" });
faux.setResponses([
  fauxAssistantMessage(
    fauxToolCall("read", { path: "package.json" }, { id: "a2e-smoke-read" }),
    { stopReason: "toolUse" },
  ),
  fauxAssistantMessage("A2E Pi monitor smoke test completed."),
]);

const modelRuntime = await ModelRuntime.create({
  authPath: join(agentDir, "auth.json"),
  modelsPath: null,
  refreshOnCreate: false,
});
modelRuntime.registerNativeProvider(faux.provider);
await modelRuntime.setRuntimeApiKey("faux", "test-only");

const { session } = await createAgentSession({
  cwd: packageRoot,
  agentDir,
  model: faux.getModel(),
  modelRuntime,
  thinkingLevel: "off",
  tools: ["read"],
  resourceLoader: loader,
  sessionManager: SessionManager.inMemory(packageRoot),
});

const eventCounts = new Map<string, number>();
session.subscribe((event) => {
  eventCounts.set(event.type, (eventCounts.get(event.type) ?? 0) + 1);
});
const fauxStream = faux.provider.streamSimple;
session.agent.streamFunction = async (model, context, options) => {
  await options?.onPayload?.(
    { model: model.id, messages: context.messages, tools: context.tools },
    model,
  );
  return fauxStream(model, context, options);
};

try {
  await session.prompt("Read package.json and confirm the A2E monitor smoke test.");
  await session.extensionRunner.emit({ type: "session_shutdown", reason: "quit" });
  console.log(JSON.stringify({
    piVersion: "0.84.1",
    modelCalls: faux.state.callCount,
    eventCounts: Object.fromEntries(eventCounts),
    collector: process.env.A2E_COLLECTOR_ENDPOINT ?? "http://127.0.0.1:6006",
    project: process.env.A2E_PROJECT_NAME ?? "default",
  }, null, 2));
} finally {
  session.dispose();
  await rm(agentDir, { recursive: true, force: true });
}
