import { spawn } from "node:child_process";
import { dirname, join, resolve } from "node:path";
import { fileURLToPath } from "node:url";

const packageRoot = resolve(dirname(fileURLToPath(import.meta.url)), "..");
const provider = process.env.A2E_PI_LIVE_PROVIDER;
const model = process.env.A2E_PI_LIVE_MODEL;
const collector = process.env.A2E_COLLECTOR_ENDPOINT ?? "http://127.0.0.1:6006";
const project = process.env.A2E_PROJECT_NAME ?? `pi-agent-live-${Date.now()}`;

if (!provider || !model) {
  console.error(
    "Set A2E_PI_LIVE_PROVIDER and A2E_PI_LIVE_MODEL before running the live smoke test.",
  );
  process.exit(2);
}

const cli = join(
  packageRoot,
  "node_modules",
  "@earendil-works",
  "pi-coding-agent",
  "dist",
  "cli.js",
);
const startedAt = new Date(Date.now() - 1_000).toISOString();
const prompt = [
  "This is a monitor smoke test.",
  "You must use the read tool exactly once to read package.json in the current directory.",
  "Then reply with the package name in one short sentence.",
].join(" ");

console.log(JSON.stringify({ provider, model, collector, project }, null, 2));

const exitCode = await new Promise((resolveExit, reject) => {
  const child = spawn(
    process.execPath,
    [
      cli,
      "--provider",
      provider,
      "--model",
      model,
      "--extension",
      packageRoot,
      "--print",
      "--no-session",
      "--tools",
      "read",
      "--thinking",
      "off",
      "--no-context-files",
      prompt,
    ],
    {
      cwd: packageRoot,
      env: {
        ...process.env,
        A2E_COLLECTOR_ENDPOINT: collector,
        A2E_PROJECT_NAME: project,
      },
      stdio: "inherit",
    },
  );
  child.once("error", reject);
  child.once("exit", (code) => resolveExit(code ?? 1));
});

if (exitCode !== 0) {
  console.error(`Pi exited with code ${exitCode}; no trace assertion was attempted.`);
  process.exit(exitCode);
}

const apiBase = collector.replace(/\/+$/, "").replace(/\/v1\/traces$/, "");
const url = new URL(`${apiBase}/v1/projects/${encodeURIComponent(project)}/spans`);
url.searchParams.set("start_time", startedAt);
url.searchParams.set("limit", "1000");

const headers = { accept: "application/json" };
if (process.env.A2E_API_KEY) {
  headers.authorization = `Bearer ${process.env.A2E_API_KEY}`;
}

let spans = [];
let lastError;
for (let attempt = 0; attempt < 20; attempt += 1) {
  try {
    const response = await fetch(url, { headers });
    if (!response.ok) {
      throw new Error(`A2E span query returned HTTP ${response.status}`);
    }
    const body = await response.json();
    spans = Array.isArray(body.data) ? body.data : [];
    if (spans.length > 0) break;
  } catch (error) {
    lastError = error;
  }
  await new Promise((resolveWait) => setTimeout(resolveWait, 500));
}

if (spans.length === 0) {
  throw new Error(
    `No spans were found in A2E for project ${project}.${lastError ? ` ${lastError}` : ""}`,
  );
}

const traceIdOf = (span) => span.context?.trace_id ?? span.trace_id;
const kindOf = (span) =>
  span.span_kind ?? span.attributes?.["openinference.span.kind"] ?? "UNKNOWN";
const agent = spans.find((span) => kindOf(span) === "AGENT");
if (!agent) throw new Error("A2E stored spans, but the AGENT root span is missing.");

const traceId = traceIdOf(agent);
const trace = spans.filter((span) => traceIdOf(span) === traceId);
const llmCount = trace.filter((span) => kindOf(span) === "LLM").length;
const toolCount = trace.filter((span) => kindOf(span) === "TOOL").length;
if (llmCount < 1 || toolCount < 1) {
  throw new Error(
    `Incomplete trace ${traceId}: expected LLM and TOOL spans, got LLM=${llmCount}, TOOL=${toolCount}.`,
  );
}

console.log(
  JSON.stringify(
    {
      verified: true,
      traceId,
      spanCount: trace.length,
      agentCount: 1,
      llmCount,
      toolCount,
    },
    null,
    2,
  ),
);
