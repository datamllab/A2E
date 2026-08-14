import { readFileSync } from "node:fs";

import type { JsonValue, ToolDefinition } from "@deepseek-ai/dsh-tools";

export interface A2EBindingTool {
  name: string;
  description?: string;
  parameters?: Record<string, unknown>;
}

export interface A2EBindingConfig {
  endpoint: string;
  token: string;
  tools: A2EBindingTool[];
}

export interface BindingToolRegistry {
  register(definition: ToolDefinition): () => void;
}

function parseBindingConfig(path: string): A2EBindingConfig {
  const parsed = JSON.parse(readFileSync(path, "utf8")) as Partial<A2EBindingConfig>;
  if (!parsed.endpoint || !parsed.token || !Array.isArray(parsed.tools)) {
    throw new Error("invalid A2E DeepSeek binding config");
  }
  return {
    endpoint: parsed.endpoint,
    token: parsed.token,
    tools: parsed.tools.filter((tool): tool is A2EBindingTool => Boolean(tool?.name)),
  };
}

function renderResult(value: JsonValue): string {
  return typeof value === "string" ? value : JSON.stringify(value);
}

/** Register the selected A2E dataset binding as native Harness tools. */
export function installA2EBindingTools(
  tools: BindingToolRegistry,
  configPath = process.env.A2E_DEEPSEEK_BINDING_CONFIG,
): number {
  if (!configPath) return 0;
  const config = parseBindingConfig(configPath);
  for (const tool of config.tools) {
    tools.register({
      name: tool.name,
      description: tool.description ?? "",
      parameters: tool.parameters ?? { type: "object", properties: {} },
      output: {
        schema: {},
        render: (_arguments, value) => [{ type: "text", text: renderResult(value) }],
      },
      async execute(argumentsValue, exec) {
        const response = await fetch(config.endpoint, {
          method: "POST",
          headers: {
            authorization: `Bearer ${config.token}`,
            "content-type": "application/json",
          },
          body: JSON.stringify({ name: tool.name, arguments: argumentsValue }),
          signal: exec.signal,
        });
        const payload = await response.json() as { result?: JsonValue; error?: string };
        if (!response.ok || payload.error) {
          throw new Error(payload.error || `A2E binding bridge returned HTTP ${response.status}`);
        }
        return payload.result ?? null;
      },
    });
  }
  return config.tools.length;
}
