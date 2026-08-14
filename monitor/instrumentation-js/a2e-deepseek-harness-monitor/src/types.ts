export interface ContentBlock {
  type?: string;
  text?: string;
  id?: string;
  name?: string;
  arguments?: string;
  toolCallId?: string;
  content?: ContentBlock[];
  isError?: boolean;
  attachment?: unknown;
  [key: string]: unknown;
}

export interface HarnessMessage {
  id?: string;
  role?: string;
  content?: ContentBlock[];
  source?: {
    kind?: string;
    provider?: string;
    model?: string;
    callId?: string;
    [key: string]: unknown;
  };
  [key: string]: unknown;
}

export interface TokenUsage {
  inputTokens?: number;
  outputTokens?: number;
  cacheReadTokens?: number;
  cacheWriteTokens?: number;
  reasoningTokens?: number;
}

export interface RequestHeader {
  config?: {
    provider?: string;
    model?: string;
    reasoningEffort?: string;
    temperature?: number;
    maxTokens?: number;
    stop?: string[];
    [key: string]: unknown;
  };
  system?: string;
  tools?: unknown[];
  [key: string]: unknown;
}

export interface SessionHeader {
  createdAt?: number;
  cwd?: string;
  parentSession?: string;
  origin?: string;
  delegationDepth?: number;
  agentPreset?: string;
}

export interface HarnessSession {
  id: string;
  header: SessionHeader;
  deriveMessages(): HarnessMessage[];
}

export interface HarnessEvent {
  type: string;
  seq: number;
  time: number;
  data: Record<string, unknown>;
}

export interface HarnessContext {
  sessions: { list(): HarnessSession[] };
  tools: import("./binding.js").BindingToolRegistry;
  logger: { warn(message: string): void };
  on(name: string, listener: (...args: any[]) => void): unknown;
  effect(effect: () => (() => void | Promise<void>), name?: string): unknown;
}

export interface TraceLifecycle {
  forceFlush?: () => Promise<unknown>;
  shutdown?: () => Promise<unknown>;
}
