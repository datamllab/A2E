import {
  SpanStatusCode,
  context,
  trace,
  type Attributes,
  type Span,
  type Tracer,
} from "@opentelemetry/api";

import type { PiMessage, TraceLifecycle } from "./types.js";

const JSON_MIME_TYPE = "application/json";
const TEXT_MIME_TYPE = "text/plain";

export interface PiTraceMonitorOptions {
  captureContent?: boolean;
  maxAttributeLength?: number;
  lifecycle?: TraceLifecycle;
}

interface PendingAgentInput {
  prompt: string;
  images?: unknown;
  systemPrompt?: string;
}

interface ToolStartEvent {
  toolCallId: string;
  toolName: string;
  args: unknown;
}

interface ToolEndEvent {
  toolCallId: string;
  toolName: string;
  result: unknown;
  isError: boolean;
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

function contentText(content: unknown, maxLength: number): string {
  if (typeof content === "string") return content.slice(0, maxLength);
  if (!Array.isArray(content)) return safeStringify(content, maxLength);
  const parts: string[] = [];
  for (const part of content) {
    if (!isRecord(part)) {
      parts.push(String(part));
      continue;
    }
    if (part.type === "text" && typeof part.text === "string") parts.push(part.text);
    else if (part.type === "thinking" && typeof part.thinking === "string") {
      parts.push(`[thinking]\n${part.thinking}`);
    } else if (part.type === "image") {
      parts.push(`[image${typeof part.mimeType === "string" ? `: ${part.mimeType}` : ""}]`);
    }
  }
  const value = parts.join("\n");
  return (value || safeStringify(content, maxLength)).slice(0, maxLength);
}

function toolCalls(content: unknown): Record<string, unknown>[] {
  if (!Array.isArray(content)) return [];
  return content.filter(
    (part): part is Record<string, unknown> => isRecord(part) && part.type === "toolCall",
  );
}

function messageAttributes(
  prefix: string,
  message: PiMessage,
  maxLength: number,
): Attributes {
  const attributes: Attributes = {};
  const role = message.role === "toolResult" ? "tool" : (message.role ?? "message");
  attributes[`${prefix}.message.role`] = role;

  if (message.content !== undefined) {
    attributes[`${prefix}.message.content`] = contentText(message.content, maxLength);
  }
  if (typeof message.toolName === "string") {
    attributes[`${prefix}.message.name`] = message.toolName;
  }
  if (typeof message.toolCallId === "string") {
    attributes[`${prefix}.message.tool_call_id`] = message.toolCallId;
  }

  toolCalls(message.content).forEach((call, index) => {
    const callPrefix = `${prefix}.message.tool_calls.${index}.tool_call`;
    if (typeof call.id === "string") attributes[`${callPrefix}.id`] = call.id;
    if (typeof call.name === "string") attributes[`${callPrefix}.function.name`] = call.name;
    if (call.arguments !== undefined) {
      attributes[`${callPrefix}.function.arguments_json`] = safeStringify(
        call.arguments,
        maxLength,
      );
    }
  });
  return attributes;
}

function messagesAttributes(
  prefix: "llm.input_messages" | "llm.output_messages",
  messages: PiMessage[],
  maxLength: number,
): Attributes {
  return Object.assign(
    {},
    ...messages.map((message, index) => messageAttributes(`${prefix}.${index}`, message, maxLength)),
  );
}

function usageAttributes(usage: unknown): Attributes {
  if (!isRecord(usage)) return {};
  const attributes: Attributes = {};
  const input = finiteNumber(usage.input);
  const output = finiteNumber(usage.output);
  const total = finiteNumber(usage.totalTokens) ??
    (input !== undefined && output !== undefined ? input + output : undefined);
  if (input !== undefined) attributes["llm.token_count.prompt"] = input;
  if (output !== undefined) attributes["llm.token_count.completion"] = output;
  if (total !== undefined) attributes["llm.token_count.total"] = total;

  const cacheRead = finiteNumber(usage.cacheRead);
  const cacheWrite = finiteNumber(usage.cacheWrite);
  if (cacheRead !== undefined) {
    attributes["llm.token_count.prompt_details.cache_read"] = cacheRead;
  }
  if (cacheWrite !== undefined) {
    attributes["llm.token_count.prompt_details.cache_write"] = cacheWrite;
  }

  if (isRecord(usage.cost)) {
    const promptCost = finiteNumber(usage.cost.input);
    const completionCost = finiteNumber(usage.cost.output);
    const totalCost = finiteNumber(usage.cost.total);
    if (promptCost !== undefined) attributes["llm.cost.prompt"] = promptCost;
    if (completionCost !== undefined) attributes["llm.cost.completion"] = completionCost;
    if (totalCost !== undefined) attributes["llm.cost.total"] = totalCost;
  }
  return attributes;
}

function spanContext(parent: Span | undefined) {
  return parent ? trace.setSpan(context.active(), parent) : context.active();
}

function errorMessage(result: unknown): string {
  if (isRecord(result)) {
    if (typeof result.errorMessage === "string") return result.errorMessage;
    if (typeof result.message === "string") return result.message;
  }
  return "Pi operation failed";
}

/** Event-to-span adapter. It never patches Pi model or tool execution. */
export class PiTraceMonitor {
  private readonly tracer: Tracer;
  private readonly captureContent: boolean;
  private readonly maxAttributeLength: number;
  private readonly lifecycle: TraceLifecycle;
  private agentSpan: Span | undefined;
  private llmSpan: Span | undefined;
  private pendingAgentInput: PendingAgentInput | undefined;
  private llmInput: PiMessage[] = [];
  private systemPrompt: string | undefined;
  private providerStatus: number | undefined;
  private agentInputCaptured = false;
  private readonly toolSpans = new Map<string, Span>();

  constructor(tracer: Tracer, options: PiTraceMonitorOptions = {}) {
    this.tracer = tracer;
    this.captureContent = options.captureContent ?? true;
    this.maxAttributeLength = Math.max(1_024, options.maxAttributeLength ?? 262_144);
    this.lifecycle = options.lifecycle ?? {};
  }

  onBeforeAgentStart(event: {
    prompt: string;
    images?: unknown;
    systemPrompt?: string;
  }): void {
    this.pendingAgentInput = {
      prompt: event.prompt,
      ...(event.images === undefined ? {} : { images: event.images }),
      ...(event.systemPrompt === undefined ? {} : { systemPrompt: event.systemPrompt }),
    };
    this.systemPrompt = event.systemPrompt;
  }

  /** Set the system prompt when only the lower-level pi-agent-core API is available. */
  onSystemPrompt(systemPrompt: string | undefined): void {
    this.systemPrompt = systemPrompt;
  }

  onAgentStart(cwd?: string): void {
    if (this.agentSpan) this.finishAgentAsIncomplete("A new Pi agent run started");
    this.agentInputCaptured = false;
    const attributes: Attributes = {
      "openinference.span.kind": "AGENT",
      "agent.framework": "pi",
      ...(cwd ? { "metadata.cwd": cwd } : {}),
    };
    if (this.captureContent && this.pendingAgentInput) {
      attributes["input.mime_type"] = JSON_MIME_TYPE;
      attributes["input.value"] = safeStringify(
        this.pendingAgentInput,
        this.maxAttributeLength,
      );
      this.agentInputCaptured = true;
    }
    this.agentSpan = this.tracer.startSpan("pi.agent", { attributes });
    this.pendingAgentInput = undefined;
  }

  /** Capture the first user message for a core Agent run that has no before-start hook. */
  onAgentInput(message: PiMessage): void {
    if (!this.captureContent || !this.agentSpan || this.agentInputCaptured) return;
    this.agentSpan.setAttribute("input.mime_type", JSON_MIME_TYPE);
    this.agentSpan.setAttribute(
      "input.value",
      safeStringify(
        {
          message,
          ...(this.systemPrompt ? { systemPrompt: this.systemPrompt } : {}),
        },
        this.maxAttributeLength,
      ),
    );
    this.agentInputCaptured = true;
  }

  onContext(messages: PiMessage[]): void {
    const system = this.systemPrompt
      ? [{ role: "system", content: this.systemPrompt } satisfies PiMessage]
      : [];
    this.llmInput = [...system, ...messages];
  }

  onBeforeProviderRequest(payload: unknown): void {
    if (this.llmSpan) this.finishLlmAsIncomplete("A new provider request started");
    const attributes: Attributes = {
      "openinference.span.kind": "LLM",
      "llm.model_name": "unknown",
    };
    if (isRecord(payload) && typeof payload.model === "string") {
      attributes["llm.model_name"] = payload.model;
    }
    if (this.captureContent) {
      attributes["llm.invocation_parameters"] = safeStringify(
        payload,
        this.maxAttributeLength,
      );
      attributes["input.mime_type"] = JSON_MIME_TYPE;
      attributes["input.value"] = safeStringify(this.llmInput, this.maxAttributeLength);
      Object.assign(
        attributes,
        messagesAttributes("llm.input_messages", this.llmInput, this.maxAttributeLength),
      );
    }
    this.llmSpan = this.tracer.startSpan(
      `pi.llm ${String(attributes["llm.model_name"])}`,
      { attributes },
      spanContext(this.agentSpan),
    );
  }

  onProviderResponse(status: number): void {
    this.providerStatus = status;
    this.llmSpan?.setAttribute("http.response.status_code", status);
  }

  onMessageStart(message: PiMessage): void {
    if (message.role !== "assistant") return;
    const model = typeof message.model === "string" ? message.model : "unknown";
    if (this.llmSpan) {
      this.llmSpan.updateName(`pi.llm ${model}`);
      this.llmSpan.setAttribute("llm.model_name", model);
      if (typeof message.provider === "string") {
        this.llmSpan.setAttribute("llm.provider", message.provider);
        this.llmSpan.setAttribute("llm.system", message.provider);
      }
      if (typeof message.api === "string") this.llmSpan.setAttribute("llm.api", message.api);
      if (this.providerStatus !== undefined) {
        this.llmSpan.setAttribute("http.response.status_code", this.providerStatus);
      }
      return;
    }
    const attributes: Attributes = {
      "openinference.span.kind": "LLM",
      "llm.model_name": model,
      ...(typeof message.provider === "string" ? { "llm.provider": message.provider } : {}),
      ...(typeof message.provider === "string" ? { "llm.system": message.provider } : {}),
      ...(typeof message.api === "string" ? { "llm.invocation_parameters": safeStringify({ api: message.api }, this.maxAttributeLength) } : {}),
      ...(this.providerStatus !== undefined ? { "http.response.status_code": this.providerStatus } : {}),
    };
    if (this.captureContent) {
      attributes["input.mime_type"] = JSON_MIME_TYPE;
      attributes["input.value"] = safeStringify(this.llmInput, this.maxAttributeLength);
      Object.assign(
        attributes,
        messagesAttributes("llm.input_messages", this.llmInput, this.maxAttributeLength),
      );
    }
    this.llmSpan = this.tracer.startSpan(
      `pi.llm ${model}`,
      { attributes },
      spanContext(this.agentSpan),
    );
  }

  onMessageEnd(message: PiMessage): void {
    if (message.role !== "assistant" || !this.llmSpan) return;
    const span = this.llmSpan;
    this.llmSpan = undefined;
    if (this.captureContent) {
      span.setAttribute("output.mime_type", JSON_MIME_TYPE);
      span.setAttribute("output.value", safeStringify(message, this.maxAttributeLength));
      span.setAttributes(
        messagesAttributes("llm.output_messages", [message], this.maxAttributeLength),
      );
    }
    span.setAttributes(usageAttributes(message.usage));
    if (typeof message.provider === "string") span.setAttribute("llm.provider", message.provider);
    if (typeof message.model === "string") span.setAttribute("llm.model_name", message.model);
    if (message.stopReason === "error" || (this.providerStatus ?? 0) >= 400) {
      const reason = this.captureContent
        ? message.errorMessage ??
          (this.providerStatus ? `Pi model provider returned HTTP ${this.providerStatus}` : "Pi model call failed")
        : "Pi model call failed";
      span.recordException(new Error(reason));
      span.setStatus({ code: SpanStatusCode.ERROR, message: reason });
    } else {
      span.setStatus({ code: SpanStatusCode.OK });
    }
    span.end();
    this.providerStatus = undefined;
  }

  onToolStart(event: ToolStartEvent): void {
    const attributes: Attributes = {
      "openinference.span.kind": "TOOL",
      "tool.id": event.toolCallId,
      "tool.name": event.toolName,
    };
    if (this.captureContent) {
      attributes["tool.parameters"] = safeStringify(
        event.args,
        this.maxAttributeLength,
      );
      attributes["input.mime_type"] = JSON_MIME_TYPE;
      attributes["input.value"] = safeStringify(event.args, this.maxAttributeLength);
    }
    const existing = this.toolSpans.get(event.toolCallId);
    if (existing) {
      existing.setStatus({ code: SpanStatusCode.ERROR, message: "Duplicate tool start" });
      existing.end();
    }
    this.toolSpans.set(
      event.toolCallId,
      this.tracer.startSpan(
        `pi.tool ${event.toolName}`,
        { attributes },
        spanContext(this.agentSpan),
      ),
    );
  }

  onToolEnd(event: ToolEndEvent): void {
    const span = this.toolSpans.get(event.toolCallId);
    if (!span) return;
    this.toolSpans.delete(event.toolCallId);
    if (this.captureContent) {
      span.setAttribute("output.mime_type", JSON_MIME_TYPE);
      span.setAttribute("output.value", safeStringify(event.result, this.maxAttributeLength));
    }
    if (event.isError) {
      const reason = this.captureContent
        ? errorMessage(event.result)
        : "Pi tool execution failed";
      span.recordException(new Error(reason));
      span.setStatus({ code: SpanStatusCode.ERROR, message: reason });
    } else {
      span.setStatus({ code: SpanStatusCode.OK });
    }
    span.end();
  }

  onAgentEnd(messages: PiMessage[]): void {
    this.closeOpenChildren();
    const span = this.agentSpan;
    this.agentSpan = undefined;
    this.agentInputCaptured = false;
    if (!span) return;
    if (this.captureContent) {
      span.setAttribute("output.mime_type", JSON_MIME_TYPE);
      span.setAttribute("output.value", safeStringify(messages, this.maxAttributeLength));
    }
    span.setStatus({ code: SpanStatusCode.OK });
    span.end();
  }

  async forceFlush(): Promise<void> {
    await this.lifecycle.forceFlush?.();
  }

  async shutdown(): Promise<void> {
    this.closeOpenChildren();
    if (this.agentSpan) this.finishAgentAsIncomplete("Pi session shut down before agent_end");
    await this.lifecycle.forceFlush?.();
    await this.lifecycle.shutdown?.();
  }

  private closeOpenChildren(): void {
    if (this.llmSpan) this.finishLlmAsIncomplete("Pi agent ended before message_end");
    for (const [id, span] of this.toolSpans) {
      span.setStatus({ code: SpanStatusCode.ERROR, message: "Pi agent ended before tool result" });
      span.setAttribute("tool.id", id);
      span.end();
    }
    this.toolSpans.clear();
  }

  private finishLlmAsIncomplete(message: string): void {
    if (!this.llmSpan) return;
    this.llmSpan.setStatus({ code: SpanStatusCode.ERROR, message });
    this.llmSpan.end();
    this.llmSpan = undefined;
  }

  private finishAgentAsIncomplete(message: string): void {
    if (!this.agentSpan) return;
    this.closeOpenChildren();
    this.agentSpan.setStatus({ code: SpanStatusCode.ERROR, message });
    this.agentSpan.end();
    this.agentSpan = undefined;
    this.agentInputCaptured = false;
  }
}

export const _test = {
  contentText,
  messageAttributes,
  safeStringify,
  usageAttributes,
};
