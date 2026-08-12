import assert from "node:assert/strict";
import { mkdtemp, readFile, rm } from "node:fs/promises";
import { createServer } from "node:http";
import { tmpdir } from "node:os";
import { dirname, join, resolve } from "node:path";
import { fileURLToPath } from "node:url";
import { describe, it } from "node:test";

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

describe("Pi 0.84 runtime integration", () => {
  it("loads the extension and exports model plus real tool events from AgentSession", async () => {
    const bodies: Buffer[] = [];
    let receive!: () => void;
    const received = new Promise<void>((resolveReceived) => {
      receive = resolveReceived;
    });
    const server = createServer((request, response) => {
      const chunks: Buffer[] = [];
      request.on("data", (chunk: Buffer) => chunks.push(chunk));
      request.on("end", () => {
        assert.equal(request.url, "/v1/traces");
        assert.match(String(request.headers["content-type"]), /application\/x-protobuf/);
        bodies.push(Buffer.concat(chunks));
        receive();
        response.writeHead(200, { "content-type": "application/x-protobuf" });
        response.end();
      });
    });
    await new Promise<void>((resolveListen, reject) => {
      server.once("error", reject);
      server.listen(0, "127.0.0.1", resolveListen);
    });
    const address = server.address();
    assert.ok(address && typeof address === "object");

    const agentDir = await mkdtemp(join(tmpdir(), "a2e-pi-runtime-"));
    const previousEndpoint = process.env.A2E_COLLECTOR_ENDPOINT;
    const previousProject = process.env.A2E_PROJECT_NAME;
    process.env.A2E_COLLECTOR_ENDPOINT = `http://127.0.0.1:${address.port}`;
    process.env.A2E_PROJECT_NAME = "pi-runtime-integration";

    let session: Awaited<ReturnType<typeof createAgentSession>>["session"] | undefined;
    try {
      const loader = new DefaultResourceLoader({
        cwd: packageRoot,
        agentDir,
        additionalExtensionPaths: [packageRoot],
      });
      await loader.reload();
      const loaded = loader.getExtensions();
      assert.deepEqual(loaded.errors, []);
      assert.equal(loaded.extensions.length, 1);

      const faux = fauxProvider({ api: "faux", provider: "faux" });
      faux.setResponses([
        fauxAssistantMessage(
          fauxToolCall("read", { path: "package.json" }, { id: "runtime-read-1" }),
          { stopReason: "toolUse" },
        ),
        fauxAssistantMessage("The package was read successfully."),
      ]);
      const modelRuntime = await ModelRuntime.create({
        authPath: join(agentDir, "auth.json"),
        modelsPath: null,
        refreshOnCreate: false,
      });
      modelRuntime.registerNativeProvider(faux.provider);
      await modelRuntime.setRuntimeApiKey("faux", "test-only");

      ({ session } = await createAgentSession({
        cwd: packageRoot,
        agentDir,
        model: faux.getModel(),
        thinkingLevel: "off",
        tools: ["read"],
        modelRuntime,
        resourceLoader: loader,
        sessionManager: SessionManager.inMemory(packageRoot),
      }));

      const fauxStream = faux.provider.streamSimple;
      session.agent.streamFunction = async (model, context, options) => {
        await options?.onPayload?.(
          { model: model.id, messages: context.messages, tools: context.tools },
          model,
        );
        return fauxStream(model, context, options);
      };
      await session.prompt("Read package.json and confirm it worked.");
      await Promise.race([
        received,
        new Promise<never>((_resolve, reject) =>
          setTimeout(() => reject(new Error("Pi trace export timed out")), 5_000),
        ),
      ]);

      const payload = Buffer.concat(bodies).toString("utf8");
      assert.match(payload, /pi\.agent/);
      assert.match(payload, /pi\.llm faux-1/);
      assert.match(payload, /pi\.tool read/);
      assert.match(payload, /runtime-read-1/);
      assert.match(payload, /The package was read successfully\./);
      assert.equal(faux.state.callCount, 2);
    } finally {
      if (session) {
        await session.extensionRunner.emit({ type: "session_shutdown", reason: "quit" });
        session.dispose();
      }
      if (previousEndpoint === undefined) delete process.env.A2E_COLLECTOR_ENDPOINT;
      else process.env.A2E_COLLECTOR_ENDPOINT = previousEndpoint;
      if (previousProject === undefined) delete process.env.A2E_PROJECT_NAME;
      else process.env.A2E_PROJECT_NAME = previousProject;
      await new Promise<void>((resolveClose, reject) =>
        server.close((error) => (error ? reject(error) : resolveClose())),
      );
      await rm(agentDir, { recursive: true, force: true });
    }
  });

  it("captures a multi-step coding task that writes and verifies an artifact", async () => {
    const bodies: Buffer[] = [];
    let receive!: () => void;
    const received = new Promise<void>((resolveReceived) => {
      receive = resolveReceived;
    });
    const server = createServer((request, response) => {
      const chunks: Buffer[] = [];
      request.on("data", (chunk: Buffer) => chunks.push(chunk));
      request.on("end", () => {
        bodies.push(Buffer.concat(chunks));
        receive();
        response.writeHead(200, { "content-type": "application/x-protobuf" });
        response.end();
      });
    });
    await new Promise<void>((resolveListen, reject) => {
      server.once("error", reject);
      server.listen(0, "127.0.0.1", resolveListen);
    });
    const address = server.address();
    assert.ok(address && typeof address === "object");

    const agentDir = await mkdtemp(join(tmpdir(), "a2e-pi-task-agent-"));
    const workspace = await mkdtemp(join(tmpdir(), "a2e-pi-task-workspace-"));
    const previousEndpoint = process.env.A2E_COLLECTOR_ENDPOINT;
    const previousProject = process.env.A2E_PROJECT_NAME;
    process.env.A2E_COLLECTOR_ENDPOINT = `http://127.0.0.1:${address.port}`;
    process.env.A2E_PROJECT_NAME = "pi-runtime-task-integration";

    let session: Awaited<ReturnType<typeof createAgentSession>>["session"] | undefined;
    try {
      const loader = new DefaultResourceLoader({
        cwd: workspace,
        agentDir,
        additionalExtensionPaths: [packageRoot],
      });
      await loader.reload();
      assert.deepEqual(loader.getExtensions().errors, []);

      const artifact = "trajectory-monitor-task-complete\n";
      const faux = fauxProvider({ api: "faux", provider: "faux" });
      faux.setResponses([
        fauxAssistantMessage(
          fauxToolCall(
            "write",
            { path: "task-output.txt", content: artifact },
            { id: "runtime-task-write-1" },
          ),
          { stopReason: "toolUse" },
        ),
        fauxAssistantMessage(
          fauxToolCall("read", { path: "task-output.txt" }, { id: "runtime-task-read-1" }),
          { stopReason: "toolUse" },
        ),
        fauxAssistantMessage("The task artifact was created and verified."),
      ]);
      const modelRuntime = await ModelRuntime.create({
        authPath: join(agentDir, "auth.json"),
        modelsPath: null,
        refreshOnCreate: false,
      });
      modelRuntime.registerNativeProvider(faux.provider);
      await modelRuntime.setRuntimeApiKey("faux", "test-only");

      ({ session } = await createAgentSession({
        cwd: workspace,
        agentDir,
        model: faux.getModel(),
        thinkingLevel: "off",
        tools: ["write", "read"],
        modelRuntime,
        resourceLoader: loader,
        sessionManager: SessionManager.inMemory(workspace),
      }));

      const fauxStream = faux.provider.streamSimple;
      session.agent.streamFunction = async (model, context, options) => {
        await options?.onPayload?.(
          { model: model.id, messages: context.messages, tools: context.tools },
          model,
        );
        return fauxStream(model, context, options);
      };
      await session.prompt(
        "Create task-output.txt with the requested marker, then read it back to verify the task.",
      );
      await Promise.race([
        received,
        new Promise<never>((_resolve, reject) =>
          setTimeout(() => reject(new Error("Pi task trace export timed out")), 5_000),
        ),
      ]);

      assert.equal(await readFile(join(workspace, "task-output.txt"), "utf8"), artifact);
      assert.equal(faux.state.callCount, 3);
      const payload = Buffer.concat(bodies).toString("utf8");
      assert.match(payload, /pi\.agent/);
      assert.match(payload, /pi\.tool write/);
      assert.match(payload, /pi\.tool read/);
      assert.match(payload, /runtime-task-write-1/);
      assert.match(payload, /runtime-task-read-1/);
      assert.match(payload, /trajectory-monitor-task-complete/);
      assert.match(payload, /The task artifact was created and verified\./);
    } finally {
      if (session) {
        await session.extensionRunner.emit({ type: "session_shutdown", reason: "quit" });
        session.dispose();
      }
      if (previousEndpoint === undefined) delete process.env.A2E_COLLECTOR_ENDPOINT;
      else process.env.A2E_COLLECTOR_ENDPOINT = previousEndpoint;
      if (previousProject === undefined) delete process.env.A2E_PROJECT_NAME;
      else process.env.A2E_PROJECT_NAME = previousProject;
      await new Promise<void>((resolveClose, reject) =>
        server.close((error) => (error ? reject(error) : resolveClose())),
      );
      await Promise.all([
        rm(agentDir, { recursive: true, force: true }),
        rm(workspace, { recursive: true, force: true }),
      ]);
    }
  });
});
