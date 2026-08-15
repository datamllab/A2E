import type { ExtensionAPI } from "@earendil-works/pi-coding-agent";
import type { AgentEvent } from "@earendil-works/pi-agent-core";

import { dispatchPiAgentEvent } from "../src/core.js";
import { createA2EPiMonitor } from "../src/runtime.js";

function debug(error: unknown): void {
  if (["1", "true", "yes", "on"].includes((process.env.A2E_PI_MONITOR_DEBUG ?? "").toLowerCase())) {
    console.warn("[a2e-pi-monitor] tracing error (Pi execution continues):", error);
  }
}

export default function a2ePiMonitorExtension(pi: ExtensionAPI): void {
  if (["0", "false", "no", "off"].includes((process.env.A2E_PI_MONITOR_ENABLED ?? "true").toLowerCase())) {
    return;
  }

  let monitor: ReturnType<typeof createA2EPiMonitor>;
  try {
    monitor = createA2EPiMonitor();
  } catch (error) {
    debug(error);
    return;
  }

  const guard = (handler: (event: any, context: any) => unknown) =>
    (event: any, context: any): any => {
      try {
        const result = handler(event, context);
        if (result instanceof Promise) result.catch(debug);
      } catch (error) {
        debug(error);
      }
      return undefined;
    };

  const guardAsync = (handler: (event: any, context: any) => Promise<unknown>) =>
    async (event: any, context: any): Promise<void> => {
      try {
        await handler(event, context);
      } catch (error) {
        debug(error);
      }
    };

  pi.on("before_agent_start", guard((event) => monitor.onBeforeAgentStart(event)));
  pi.on("agent_start", guard((event, context) =>
    dispatchPiAgentEvent(monitor, event as AgentEvent, { cwd: context.cwd })));
  pi.on("context", guard((event) => monitor.onContext(event.messages)));
  pi.on("before_provider_request", guard((event) => monitor.onBeforeProviderRequest(event.payload)));
  pi.on("after_provider_response", guard((event) => monitor.onProviderResponse(event.status)));
  pi.on("message_start", guard((event) =>
    dispatchPiAgentEvent(monitor, event as AgentEvent)));
  pi.on("message_end", guard((event) =>
    dispatchPiAgentEvent(monitor, event as AgentEvent)));
  pi.on("tool_execution_start", guard((event) =>
    dispatchPiAgentEvent(monitor, event as AgentEvent)));
  pi.on("tool_execution_end", guard((event) =>
    dispatchPiAgentEvent(monitor, event as AgentEvent)));
  pi.on("agent_end", guard((event) => {
    dispatchPiAgentEvent(monitor, event as AgentEvent);
    void monitor.forceFlush().catch(debug);
  }));
  pi.on("session_shutdown", guardAsync(async () => monitor.shutdown()));
}
