import { readFileSync } from "node:fs";

import type { ExtensionAPI } from "@earendil-works/pi-coding-agent";
import { Unsafe } from "typebox";

interface BindingToolConfig {
  endpoint: string;
  token: string;
  systemPrompt?: string;
  tools: Array<{
    name: string;
    description?: string;
    parameters?: Record<string, unknown>;
  }>;
}

function loadConfig(): BindingToolConfig | undefined {
  const path = process.env.A2E_PI_BINDING_CONFIG;
  if (!path) return undefined;
  const value = JSON.parse(readFileSync(path, "utf8")) as BindingToolConfig;
  if (!value.endpoint.startsWith("http://127.0.0.1:")) {
    throw new Error("A2E Pi binding endpoint must use loopback");
  }
  if (!value.token || !Array.isArray(value.tools)) {
    throw new Error("Invalid A2E Pi binding configuration");
  }
  return value;
}

export default function a2ePiBindingTools(pi: ExtensionAPI): void {
  let loadedConfig: BindingToolConfig | undefined;
  try {
    loadedConfig = loadConfig();
  } catch (error) {
    console.warn("[a2e-pi-binding] configuration error:", error);
    return;
  }
  if (!loadedConfig) return;
  const config = loadedConfig;

  for (const tool of config.tools) {
    pi.registerTool({
      name: tool.name,
      label: tool.name,
      description: tool.description || `A2E benchmark tool: ${tool.name}`,
      parameters: Unsafe<Record<string, unknown>>(
        tool.parameters || { type: "object", properties: {} },
      ),
      executionMode: "sequential",
      async execute(_toolCallId, params, signal) {
        const response = await fetch(config.endpoint, {
          method: "POST",
          headers: {
            authorization: `Bearer ${config.token}`,
            "content-type": "application/json",
          },
          body: JSON.stringify({ name: tool.name, arguments: params }),
          ...(signal ? { signal } : {}),
        });
        const body = await response.text();
        if (!response.ok) {
          throw new Error(`A2E benchmark tool ${tool.name} failed (${response.status}): ${body}`);
        }
        const result = JSON.parse(body) as { result: unknown };
        const text = typeof result.result === "string"
          ? result.result
          : JSON.stringify(result.result);
        return {
          content: [{ type: "text", text: text ?? "null" }],
          details: { result: result.result },
        };
      },
    });
  }

  if (config.systemPrompt) {
    pi.on("before_agent_start", (event) => ({
      systemPrompt: `${event.systemPrompt}\n\n${config.systemPrompt}`,
    }));
  }
}
