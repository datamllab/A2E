import { createA2EDeepSeekMonitor } from "./runtime.js";
import { installA2EBindingTools } from "./binding.js";
import type { HarnessContext, HarnessEvent, HarnessSession } from "./types.js";

/** Loadable Cordis plugin used by DeepSeek Harness profiles. */
export default class A2EDeepSeekHarnessMonitorPlugin {
  static inject = ["sessions", "tools"];

  constructor(ctx: HarnessContext) {
    const monitor = createA2EDeepSeekMonitor(process.env);
    const contain = (operation: () => void): void => {
      try {
        operation();
      } catch (error) {
        ctx.logger.warn(`a2e-deepseek-harness-monitor: ${String(error)}`);
      }
    };

    contain(() => {
      installA2EBindingTools(ctx.tools);
    });

    ctx.on("session/created", (session: HarnessSession) => {
      contain(() => monitor.onSessionCreated(session));
    });
    ctx.on("session/event", (session: HarnessSession, event: HarnessEvent) => {
      contain(() => monitor.onSessionEvent(session, event));
    });
    ctx.on("session/disposed", (session: HarnessSession) => {
      contain(() => monitor.onSessionDisposed(session));
    });

    for (const session of ctx.sessions.list()) {
      contain(() => monitor.onSessionCreated(session));
    }

    ctx.effect(() => async () => {
      try {
        await monitor.shutdown();
      } catch (error) {
        ctx.logger.warn(`a2e-deepseek-harness-monitor: shutdown failed: ${String(error)}`);
      }
    }, "A2E DeepSeek Harness monitor");
  }
}

export { DeepSeekTraceMonitor } from "./monitor.js";
export {
  createA2EDeepSeekMonitor,
  extractParentContext,
  normalizeTraceEndpoint,
  parseHeaders,
  resolveRuntimeConfig,
} from "./runtime.js";
export type * from "./types.js";
