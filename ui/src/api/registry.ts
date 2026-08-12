import { fetchJSON } from "./client";
import type { AgentInfo } from "./types";
import { AGENT_FALLBACK } from "../utils/constants";

export async function getAgents(): Promise<AgentInfo[]> {
  try {
    const data = await fetchJSON<{ agents?: string[]; agent_meta?: Record<string, { label?: string }> }>(
      "/v1/a2e/registry",
    );
    const names = data.agents ?? [];
    if (!names.length) return AGENT_FALLBACK;
    return names.map((id) => ({
      id,
      label: data.agent_meta?.[id]?.label ?? id,
    }));
  } catch {
    return AGENT_FALLBACK;
  }
}
