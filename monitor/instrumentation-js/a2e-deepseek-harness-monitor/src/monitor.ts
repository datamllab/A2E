import {
  SpanStatusCode,
  context,
  trace,
  type Attributes,
  type Context,
  type Span,
  type Tracer,
} from "@opentelemetry/api";

import type {
  ContentBlock,
  HarnessEvent,
  HarnessMessage,
  HarnessSession,
  RequestHeader,
  TokenUsage,
  TraceLifecycle,
} from "./types.js";

const JSON_MIME_TYPE = "application/json";

export interface DeepSeekTraceMonitorOptions {
  captureContent?: boolean;
  maxAttributeLength?: number;
  parentContext?: Context;
  lifecycle?: TraceLifecycle;
}

interface LlmState {
  span: Span;
  turn: number;
  step: number;
}

interface ToolState {
  span: Span;
  turn: number;
  step: number;
  name: string;
}

interface TurnState {
  span: Span;
  turn: number;
  input: HarnessMessage[];
  output: unknown[];
  llms: Map<string, LlmState>;
  tools: Map<string, ToolState>;
}

interface SessionState {
  header?: RequestHeader;
  turn?: TurnState;
}

function isRecord(value: unknown): value is Record<string, unknown> {
  return typeof value === "object" && value !== null;
}

function finiteNumber(value: unknown): number | undefined {
  return typeof value === "number" && Number.isFinite(value) ? value : undefined;
}

function safeStringify(value: unknown, maxLength: number): string {
  const seen = new WeakSet<object>();
  let serialized: string;
  try {
    serialized = JSON.stringify(value, (_key, item: unknown) => {
      if (typeof item === "bigint") return item.toString();
      if (item instanceof Error) {
        return { name: item.name, message: item.message, stack: item.stack };
      }
      if (typeof item === "object" && item !== null) {
        if (seen.has(item)) return "[Circular]";
        seen.add(item);
      }
      return item;
    });
  } catch (error) {
    serialized = JSON.stringify({ serializationError: String(error), value: String(value) });
  }
  if (serialized === undefined) serialized = String(value);
  if (serialized.length <= maxLength) return serialized;
  return JSON.stringify({
    _a2e_truncated: true,
    original_length: serialized.length,
    preview: serialized.slice(0, Math.max(0, maxLength - 100)),
  });
}

function bounded(value: string, maxLength: number): string {
  return value.length <= maxLength ? value : value.slice(0, maxLength);
}

function blockText(block: ContentBlock, maxLength: number): string {
  if ((block.type === "text" || block.type === "reasoning") && typeof block.text === "string") {
    return block.type === "reasoning" ? `[reasoning]\n${block.text}` : block.text;
  }
  if (block.type === "image") return "[image]";
  if (block.type === "tool-call") {
    return `[tool-call ${typeof block.name === "string" ? block.name : "unknown"}]`;
  }
  if (block.type === "tool-result" && Array.isArray(block.content)) {
    return block.content.map((item) => blockText(item, maxLength)).join("\n");
  }
  return safeStringify(block, maxLength);
}

function contentText(content: unknown, maxLength: number): string {
  if (!Array.isArray(content)) return safeStringify(content, maxLength);
  const text = content
    .map((block) => isRecord(block) ? blockText(block as ContentBlock, maxLength) : String(block))
    .join("\n");
  return bounded(text, maxLength);
}

function messageRole(message: HarnessMessage): string {
  return message.source?.kind === "tool" ? "tool" : (message.role ?? "message");
}

function messageAttributes(prefix: string, message: HarnessMessage, maxLength: number): Attributes {
  const attributes: Attributes = {
    [`${prefix}.message.role`]: messageRole(message),
  };
  if (message.content !== undefined) {
    attributes[`${prefix}.message.content`] = contentText(message.content, maxLength);
  }
  if (message.source?.kind === "tool" && typeof message.source.callId === "string") {
    attributes[`${prefix}.message.tool_call_id`] = message.source.callId;
  }
  if (!Array.isArray(message.content)) return attributes;
  let toolIndex = 0;
  for (const block of message.content) {
    if (!isRecord(block) || block.type !== "tool-call") continue;
    const callPrefix = `${prefix}.message.tool_calls.${toolIndex++}.tool_call`;
    if (typeof block.id === "string") attributes[`${callPrefix}.id`] = block.id;
    if (typeof block.name === "string") attributes[`${callPrefix}.function.name`] = block.name;
    if (typeof block.arguments === "string") {
      attributes[`${callPrefix}.function.arguments_json`] = bounded(block.arguments, maxLength);
    }
  }
  return attributes;
}

function messagesAttributes(
  prefix: "llm.input_messages" | "llm.output_messages",
  messages: HarnessMessage[],
  maxLength: number,
): Attributes {
  return Object.assign(
    {},
    ...messages.map((message, index) => messageAttributes(`${prefix}.${index}`, message, maxLength)),
  );
}

function usageAttributes(value: unknown): Attributes {
  if (!isRecord(value)) return {};
  const usage = value as TokenUsage;
  const uncached = finiteNumber(usage.inputTokens);
  const cacheRead = finiteNumber(usage.cacheReadTokens);
  const cacheWrite = finiteNumber(usage.cacheWriteTokens);
  const completion = finiteNumber(usage.outputTokens);
  const reasoning = finiteNumber(usage.reasoningTokens);
  const prompt = uncached === undefined && cacheRead === undefined && cacheWrite === undefined
    ? undefined
    : (uncached ?? 0) + (cacheRead ?? 0) + (cacheWrite ?? 0);
  const attributes: Attributes = {};
  if (prompt !== undefined) attributes["llm.token_count.prompt"] = prompt;
  if (completion !== undefined) attributes["llm.token_count.completion"] = completion;
  if (prompt !== undefined || completion !== undefined) {
    attributes["llm.token_count.total"] = (prompt ?? 0) + (completion ?? 0);
  }
  if (cacheRead !== undefined) {
    attributes["llm.token_count.prompt_details.cache_read"] = cacheRead;
  }
  if (cacheWrite !== undefined) {
    attributes["llm.token_count.prompt_details.cache_write"] = cacheWrite;
  }
  if (reasoning !== undefined) {
    attributes["llm.token_count.completion_details.reasoning"] = reasoning;
  }
  return attributes;
}

function childContext(parent: Span): Context {
  return trace.setSpan(context.active(), parent);
}

function key(turn: number, step: number): string {
  return `${turn}:${step}`;
}

function eventNumber(data: Record<string, unknown>, field: "turn" | "step"): number | undefined {
  const value = finiteNumber(data[field]);
  return value !== undefined && Number.isSafeInteger(value) ? value : undefined;
}

function eventDate(time: number): Date {
  return new Date(Number.isFinite(time) ? time : Date.now());
}

function toolResultIsError(message: unknown): boolean {
  if (!isRecord(message) || !Array.isArray(message.content)) return false;
  return message.content.some(
    (block) => isRecord(block) && block.type === "tool-result" && block.isError === true,
  );
}

function turnReason(value: unknown): { kind: string; message?: string } {
  if (!isRecord(value) || typeof value.kind !== "string") return { kind: "unknown" };
  if (value.kind === "error" && isRecord(value.error) && typeof value.error.message === "string") {
    return { kind: value.kind, message: value.error.message };
  }
  return { kind: value.kind };
}

/** Converts DeepSeek Harness's durable session events into A2E OpenInference spans. */
export class DeepSeekTraceMonitor {
  private readonly sessions = new Map<HarnessSession, SessionState>();
  private readonly captureContent: boolean;
  private readonly maxAttributeLength: number;
  private readonly parentContext: Context | undefined;
  private readonly lifecycle: TraceLifecycle;

  constructor(private readonly tracer: Tracer, options: DeepSeekTraceMonitorOptions = {}) {
    this.captureContent = options.captureContent ?? true;
    this.maxAttributeLength = Math.max(1_024, options.maxAttributeLength ?? 262_144);
    this.parentContext = options.parentContext;
    this.lifecycle = options.lifecycle ?? {};
  }

  onSessionCreated(session: HarnessSession): void {
    this.sessions.set(session, {});
  }

  onSessionEvent(session: HarnessSession, event: HarnessEvent): void {
    const state = this.state(session);
    switch (event.type) {
      case "turn/start":
        this.startTurn(session, state, event);
        break;
      case "user/message":
        this.userMessage(session, state, event);
        break;
      case "step/start":
        this.startStep(session, state, event);
        break;
      case "request/header":
        this.requestHeader(session, state, event);
        break;
      case "assistant/message":
        this.assistantMessage(state, event);
        break;
      case "tool/call":
        this.toolCall(state, event);
        break;
      case "tool/result":
        this.toolResult(state, event);
        break;
      case "step/end":
        this.endStep(state, event, "DeepSeek Harness step ended before all operations completed");
        break;
      case "turn/end":
        this.endTurn(state, event);
        break;
      default:
        break;
    }
  }

  onSessionDisposed(session: HarnessSession): void {
    const state = this.sessions.get(session);
    if (state?.turn) {
      this.finishTurn(state, state.turn, Date.now(), {
        kind: "disposed",
        message: "DeepSeek Harness session was disposed before turn/end",
      });
    }
    this.sessions.delete(session);
  }

  async forceFlush(): Promise<void> {
    await this.lifecycle.forceFlush?.();
  }

  async shutdown(): Promise<void> {
    for (const [session, state] of this.sessions) this.onSessionDisposed(session);
    await this.lifecycle.forceFlush?.();
    await this.lifecycle.shutdown?.();
  }

  private state(session: HarnessSession): SessionState {
    let state = this.sessions.get(session);
    if (!state) {
      state = {};
      this.sessions.set(session, state);
    }
    return state;
  }

  private startTurn(session: HarnessSession, state: SessionState, event: HarnessEvent): void {
    const turn = eventNumber(event.data, "turn");
    if (turn === undefined) return;
    if (state.turn) {
      this.finishTurn(state, state.turn, event.time, {
        kind: "incomplete",
        message: "A new DeepSeek Harness turn started before turn/end",
      });
    }
    const header = session.header ?? {};
    const attributes: Attributes = {
      "openinference.span.kind": "AGENT",
      "agent.framework": "deepseek-harness",
      "session.id": session.id,
      "agent.turn": turn,
      ...(header.cwd ? { "metadata.cwd": header.cwd } : {}),
      ...(header.parentSession ? { "session.parent_id": header.parentSession } : {}),
      ...(header.origin ? { "session.origin": header.origin } : {}),
      ...(header.delegationDepth !== undefined
        ? { "session.delegation_depth": header.delegationDepth }
        : {}),
      ...(header.agentPreset ? { "agent.preset": header.agentPreset } : {}),
    };
    const span = this.tracer.startSpan(
      "deepseek-harness.agent",
      { attributes, startTime: eventDate(event.time) },
      this.parentContext,
    );
    state.turn = { span, turn, input: [], output: [], llms: new Map(), tools: new Map() };
  }

  private userMessage(session: HarnessSession, state: SessionState, event: HarnessEvent): void {
    const turn = state.turn;
    if (!turn) return;
    const message = event.data as HarnessMessage;
    turn.input.push(message);
    if (!this.captureContent) return;
    const input = {
      messages: turn.input,
      ...(state.header?.system ? { system: state.header.system } : {}),
    };
    turn.span.setAttribute("input.mime_type", JSON_MIME_TYPE);
    turn.span.setAttribute("input.value", safeStringify(input, this.maxAttributeLength));
    // Keep the current derived transcript available for request/header even in
    // integrations whose Session implementation computes messages lazily.
    try {
      session.deriveMessages();
    } catch {
      // A presentation helper must never affect the agent loop.
    }
  }

  private startStep(session: HarnessSession, state: SessionState, event: HarnessEvent): void {
    const turnNumber = eventNumber(event.data, "turn");
    const step = eventNumber(event.data, "step");
    const turn = state.turn;
    if (!turn || turnNumber === undefined || step === undefined || turn.turn !== turnNumber) return;
    const stepKey = key(turnNumber, step);
    const existing = turn.llms.get(stepKey);
    if (existing) this.finishLlm(turn, stepKey, existing, event.time, false, "Duplicate step/start");
    const provider = state.header?.config?.provider ?? "unknown";
    const model = state.header?.config?.model ?? "unknown";
    const span = this.tracer.startSpan(
      `deepseek-harness.llm ${model}`,
      {
        startTime: eventDate(event.time),
        attributes: {
          "openinference.span.kind": "LLM",
          "llm.model_name": model,
          "llm.provider": provider,
          "llm.system": provider,
          "agent.turn": turnNumber,
          "agent.step": step,
          "session.id": session.id,
        },
      },
      childContext(turn.span),
    );
    const llm = { span, turn: turnNumber, step };
    turn.llms.set(stepKey, llm);
    // Harness logs a request/header only when the request epoch changes. A
    // later step in the same epoch still makes a new model request, so reuse
    // the most recent header and take a fresh derived-message snapshot here.
    if (state.header) this.applyRequestHeader(session, turn, llm, state.header);
  }

  private requestHeader(session: HarnessSession, state: SessionState, event: HarnessEvent): void {
    if (!isRecord(event.data.header)) return;
    const header = event.data.header as RequestHeader;
    state.header = header;
    const turn = state.turn;
    if (!turn) return;
    let step = -1;
    for (const candidate of turn.llms.values()) step = Math.max(step, candidate.step);
    if (step < 0) return;
    const llm = turn.llms.get(key(turn.turn, step));
    if (!llm) return;
    this.applyRequestHeader(session, turn, llm, header);
  }

  private applyRequestHeader(
    session: HarnessSession,
    turn: TurnState,
    llm: LlmState,
    header: RequestHeader,
  ): void {
    const provider = header.config?.provider ?? "unknown";
    const model = header.config?.model ?? "unknown";
    llm.span.updateName(`deepseek-harness.llm ${model}`);
    llm.span.setAttribute("llm.model_name", model);
    llm.span.setAttribute("llm.provider", provider);
    llm.span.setAttribute("llm.system", provider);
    if (!this.captureContent) return;
    llm.span.setAttribute(
      "llm.invocation_parameters",
      safeStringify(header.config ?? {}, this.maxAttributeLength),
    );
    if (header.tools) {
      llm.span.setAttribute("llm.tools", safeStringify(header.tools, this.maxAttributeLength));
    }
    let messages: HarnessMessage[] = [];
    try {
      messages = session.deriveMessages();
    } catch {
      messages = [...turn.input];
    }
    if (header.system) {
      messages = [{ role: "system", content: [{ type: "text", text: header.system }] }, ...messages];
    }
    llm.span.setAttribute("input.mime_type", JSON_MIME_TYPE);
    llm.span.setAttribute("input.value", safeStringify(messages, this.maxAttributeLength));
    llm.span.setAttributes(messagesAttributes("llm.input_messages", messages, this.maxAttributeLength));
    const agentInput = {
      messages: turn.input,
      ...(header.system ? { system: header.system } : {}),
    };
    turn.span.setAttribute("input.mime_type", JSON_MIME_TYPE);
    turn.span.setAttribute("input.value", safeStringify(agentInput, this.maxAttributeLength));
  }

  private assistantMessage(state: SessionState, event: HarnessEvent): void {
    const turnNumber = eventNumber(event.data, "turn");
    const step = eventNumber(event.data, "step");
    const turn = state.turn;
    if (!turn || turnNumber === undefined || step === undefined || turn.turn !== turnNumber) return;
    const message = isRecord(event.data.message)
      ? event.data.message as HarnessMessage
      : { role: "assistant", content: [] };
    turn.output.push(message);
    const stepKey = key(turnNumber, step);
    const llm = turn.llms.get(stepKey);
    if (!llm) return;
    const provider = message.source?.provider ?? state.header?.config?.provider;
    const model = message.source?.model ?? state.header?.config?.model;
    if (provider) {
      llm.span.setAttribute("llm.provider", provider);
      llm.span.setAttribute("llm.system", provider);
    }
    if (model) {
      llm.span.setAttribute("llm.model_name", model);
      llm.span.updateName(`deepseek-harness.llm ${model}`);
    }
    if (this.captureContent) {
      llm.span.setAttribute("output.mime_type", JSON_MIME_TYPE);
      llm.span.setAttribute("output.value", safeStringify(message, this.maxAttributeLength));
      llm.span.setAttributes(
        messagesAttributes("llm.output_messages", [message], this.maxAttributeLength),
      );
    }
    llm.span.setAttributes(usageAttributes(event.data.usage));
    this.finishLlm(turn, stepKey, llm, event.time, true);
  }

  private toolCall(state: SessionState, event: HarnessEvent): void {
    const turnNumber = eventNumber(event.data, "turn");
    const step = eventNumber(event.data, "step");
    const turn = state.turn;
    const callId = typeof event.data.callId === "string" ? event.data.callId : undefined;
    const name = typeof event.data.name === "string" ? event.data.name : "unknown";
    if (!turn || turnNumber === undefined || step === undefined || !callId || turn.turn !== turnNumber) return;
    const existing = turn.tools.get(callId);
    if (existing) this.finishTool(turn, callId, existing, event.time, false, "Duplicate tool/call");
    const rawArguments = typeof event.data.arguments === "string"
      ? event.data.arguments
      : safeStringify(event.data.arguments, this.maxAttributeLength);
    const attributes: Attributes = {
      "openinference.span.kind": "TOOL",
      "tool.id": callId,
      "tool.name": name,
      "agent.turn": turnNumber,
      "agent.step": step,
    };
    if (this.captureContent) {
      attributes["tool.parameters"] = bounded(rawArguments, this.maxAttributeLength);
      attributes["input.mime_type"] = JSON_MIME_TYPE;
      attributes["input.value"] = bounded(rawArguments, this.maxAttributeLength);
    }
    const span = this.tracer.startSpan(
      `deepseek-harness.tool ${name}`,
      { attributes, startTime: eventDate(event.time) },
      childContext(turn.span),
    );
    turn.tools.set(callId, { span, turn: turnNumber, step, name });
  }

  private toolResult(state: SessionState, event: HarnessEvent): void {
    const turnNumber = eventNumber(event.data, "turn");
    const step = eventNumber(event.data, "step");
    const turn = state.turn;
    const message = event.data.message;
    const source = isRecord(message) && isRecord(message.source) ? message.source : undefined;
    const callId = source && typeof source.callId === "string" ? source.callId : undefined;
    if (!turn || turnNumber === undefined || step === undefined || !callId || turn.turn !== turnNumber) return;
    turn.output.push(message);
    const tool = turn.tools.get(callId);
    if (!tool) return;
    const failed = toolResultIsError(message) || event.data.error !== undefined;
    if (this.captureContent) {
      tool.span.setAttribute("output.mime_type", JSON_MIME_TYPE);
      tool.span.setAttribute("output.value", safeStringify(message, this.maxAttributeLength));
    }
    const internalError = isRecord(event.data.error) && typeof event.data.error.code === "string"
      ? `${event.data.error.name ?? "ToolError"}: ${event.data.error.code}`
      : undefined;
    const contentError = this.captureContent && failed ? contentText((message as HarnessMessage)?.content, this.maxAttributeLength) : undefined;
    this.finishTool(
      turn,
      callId,
      tool,
      event.time,
      !failed,
      failed ? (contentError || internalError || "DeepSeek Harness tool execution failed") : undefined,
    );
  }

  private endStep(state: SessionState, event: HarnessEvent, message: string): void {
    const turnNumber = eventNumber(event.data, "turn");
    const step = eventNumber(event.data, "step");
    const turn = state.turn;
    if (!turn || turnNumber === undefined || step === undefined) return;
    const stepKey = key(turnNumber, step);
    const llm = turn.llms.get(stepKey);
    if (llm) this.finishLlm(turn, stepKey, llm, event.time, false, message);
    for (const [callId, tool] of turn.tools) {
      if (tool.turn === turnNumber && tool.step === step) {
        this.finishTool(turn, callId, tool, event.time, false, message);
      }
    }
  }

  private endTurn(state: SessionState, event: HarnessEvent): void {
    const turnNumber = eventNumber(event.data, "turn");
    const turn = state.turn;
    if (!turn || turnNumber === undefined || turn.turn !== turnNumber) return;
    const reason = turnReason(event.data.reason);
    this.finishTurn(state, turn, event.time, reason);
  }

  private finishTurn(
    state: SessionState,
    turn: TurnState,
    time: number,
    reason: { kind: string; message?: string },
  ): void {
    for (const [stepKey, llm] of turn.llms) {
      this.finishLlm(turn, stepKey, llm, time, false, "DeepSeek Harness turn ended before model output");
    }
    for (const [callId, tool] of turn.tools) {
      this.finishTool(turn, callId, tool, time, false, "DeepSeek Harness turn ended before tool result");
    }
    turn.span.setAttribute("agent.turn_end_reason", reason.kind);
    if (this.captureContent) {
      turn.span.setAttribute("output.mime_type", JSON_MIME_TYPE);
      turn.span.setAttribute("output.value", safeStringify(turn.output, this.maxAttributeLength));
    }
    const ok = reason.kind === "completed" || reason.kind === "max-tokens";
    if (ok) {
      turn.span.setStatus({ code: SpanStatusCode.OK });
    } else {
      const message = this.captureContent && reason.message
        ? reason.message
        : `DeepSeek Harness turn ended: ${reason.kind}`;
      turn.span.setStatus({ code: SpanStatusCode.ERROR, message });
      if (this.captureContent && reason.message) turn.span.recordException(new Error(reason.message));
    }
    turn.span.end(eventDate(time));
    if (state.turn === turn) delete state.turn;
  }

  private finishLlm(
    turn: TurnState,
    stepKey: string,
    llm: LlmState,
    time: number,
    ok: boolean,
    message?: string,
  ): void {
    turn.llms.delete(stepKey);
    llm.span.setStatus(ok
      ? { code: SpanStatusCode.OK }
      : { code: SpanStatusCode.ERROR, message: message ?? "DeepSeek Harness model call failed" });
    llm.span.end(eventDate(time));
  }

  private finishTool(
    turn: TurnState,
    callId: string,
    tool: ToolState,
    time: number,
    ok: boolean,
    message?: string,
  ): void {
    turn.tools.delete(callId);
    const errorMessage = message ?? "DeepSeek Harness tool execution failed";
    if (ok) tool.span.setStatus({ code: SpanStatusCode.OK });
    else {
      tool.span.setStatus({ code: SpanStatusCode.ERROR, message: errorMessage });
      if (this.captureContent && message) tool.span.recordException(new Error(errorMessage));
    }
    tool.span.end(eventDate(time));
  }
}

export const _test = {
  contentText,
  messageAttributes,
  safeStringify,
  usageAttributes,
};
