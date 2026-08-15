import type {
  Agent,
  AgentEvent,
  AgentMessage,
} from "@earendil-works/pi-agent-core";

import { PiTraceMonitor } from "./monitor.js";
import {
  createA2EPiMonitor,
  type PiMonitorEnvironment,
} from "./runtime.js";
import type { PiMessage } from "./types.js";

export interface PiAgentEventSnapshot {
  cwd?: string;
  systemPrompt?: string;
  messages?: AgentMessage[];
}

export interface InstrumentPiAgentOptions {
  /** Working directory recorded on the AGENT span. */
  cwd?: string;
  /** Inject a monitor, primarily for custom exporters and tests. */
  monitor?: PiTraceMonitor;
  /** Environment used when this function creates its own A2E monitor. */
  env?: PiMonitorEnvironment;
  /** Receives tracing failures. Failures are always isolated from the Agent. */
  onError?: (error: unknown) => void;
}

export interface PiAgentInstrumentation {
  readonly monitor: PiTraceMonitor;
  /** Stop observing events without shutting down an injected monitor. */
  dispose(): void;
  /** Stop observing, flush pending spans, and shut down the monitor. */
  shutdown(): Promise<void>;
}

type SubscribablePiAgent = Pick<
  Agent,
  "state" | "subscribe" | "onPayload" | "onResponse"
>;

function piMessage(message: AgentMessage): PiMessage {
  return message as PiMessage;
}

function piMessages(messages: AgentMessage[]): PiMessage[] {
  return messages as PiMessage[];
}

/**
 * Map the public pi-agent-core lifecycle onto the shared OpenInference monitor.
 * pi-coding-agent reuses this dispatcher and adds its higher-level events.
 */
export function dispatchPiAgentEvent(
  monitor: PiTraceMonitor,
  event: AgentEvent,
  snapshot: PiAgentEventSnapshot = {},
): void {
  switch (event.type) {
    case "agent_start":
      if (snapshot.systemPrompt !== undefined) {
        monitor.onSystemPrompt(snapshot.systemPrompt);
      }
      monitor.onAgentStart(snapshot.cwd);
      return;
    case "message_start":
      if (event.message.role === "user") monitor.onAgentInput(piMessage(event.message));
      if (event.message.role === "assistant" && snapshot.messages) {
        monitor.onContext(piMessages(snapshot.messages));
      }
      monitor.onMessageStart(piMessage(event.message));
      return;
    case "message_end":
      monitor.onMessageEnd(piMessage(event.message));
      return;
    case "tool_execution_start":
      monitor.onToolStart(event);
      return;
    case "tool_execution_end":
      monitor.onToolEnd(event);
      return;
    case "agent_end":
      monitor.onAgentEnd(piMessages(event.messages));
      return;
    case "turn_start":
    case "turn_end":
    case "message_update":
    case "tool_execution_update":
      return;
  }
}

/** Instrument a standalone pi-agent-core Agent through its public subscribe API. */
export function instrumentPiAgent(
  agent: SubscribablePiAgent,
  options: InstrumentPiAgentOptions = {},
): PiAgentInstrumentation {
  const monitor = options.monitor ?? createA2EPiMonitor(options.env);
  const report = (error: unknown): void => {
    try {
      options.onError?.(error);
    } catch {
      // Observability must never alter the Agent's execution path.
    }
  };
  let active = true;
  const originalOnPayload = agent.onPayload;
  const originalOnResponse = agent.onResponse;

  const wrappedOnPayload: NonNullable<Agent["onPayload"]> = async (payload, model) => {
    const replacement = await originalOnPayload?.(payload, model);
    try {
      monitor.onContext(piMessages(agent.state.messages));
      monitor.onBeforeProviderRequest(replacement ?? payload);
    } catch (error) {
      report(error);
    }
    return replacement;
  };
  const wrappedOnResponse: NonNullable<Agent["onResponse"]> = async (response, model) => {
    try {
      monitor.onProviderResponse(response.status);
    } catch (error) {
      report(error);
    }
    await originalOnResponse?.(response, model);
  };
  agent.onPayload = wrappedOnPayload;
  agent.onResponse = wrappedOnResponse;

  const unsubscribe = agent.subscribe((event) => {
    try {
      const snapshot: PiAgentEventSnapshot = {
        systemPrompt: agent.state.systemPrompt,
        messages: agent.state.messages,
        ...(options.cwd === undefined ? {} : { cwd: options.cwd }),
      };
      dispatchPiAgentEvent(monitor, event, snapshot);
      if (event.type === "agent_end") void monitor.forceFlush().catch(report);
    } catch (error) {
      report(error);
    }
  });

  const dispose = (): void => {
    if (!active) return;
    active = false;
    unsubscribe();
    if (agent.onPayload === wrappedOnPayload) agent.onPayload = originalOnPayload;
    if (agent.onResponse === wrappedOnResponse) agent.onResponse = originalOnResponse;
  };

  return {
    monitor,
    dispose,
    async shutdown(): Promise<void> {
      dispose();
      try {
        await monitor.shutdown();
      } catch (error) {
        report(error);
      }
    },
  };
}
