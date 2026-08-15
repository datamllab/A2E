export interface PiMessage {
  role?: string;
  content?: unknown;
  provider?: string;
  model?: string;
  api?: string;
  usage?: unknown;
  stopReason?: string;
  errorMessage?: string;
  toolCallId?: string;
  toolName?: string;
}

export interface TraceLifecycle {
  forceFlush?: () => Promise<unknown>;
  shutdown?: () => Promise<unknown>;
}
