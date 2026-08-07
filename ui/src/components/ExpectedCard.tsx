import { esc, pretty } from "../utils/format";

function answerSnippet(answer: unknown, needle: unknown): string {
  const text = String(answer ?? "");
  const q = String(needle ?? "");
  const idx = text.toLowerCase().indexOf(q.toLowerCase());
  if (idx < 0) return "";
  const start = Math.max(0, idx - 36);
  const end = Math.min(text.length, idx + q.length + 36);
  return `${start ? "..." : ""}${text.slice(start, end)}${end < text.length ? "..." : ""}`;
}

function ExpectedCheckRow({
  ok,
  expected,
  observed,
  detail = "",
}: {
  ok: boolean;
  expected: string;
  observed: string;
  detail?: string;
}) {
  return (
    <div className={`expected-check ${ok ? "pass" : "miss"}`}>
      <span className={`expected-step ${ok ? "pass" : "miss"}`}>{ok ? "✓" : "×"}</span>
      <div className="expected-main">
        <div className="expected-pair">
          <span>Expected</span>
          <strong>{esc(expected)}</strong>
        </div>
        {detail ? <pre className="expected-args">{esc(detail)}</pre> : null}
        <div className="expected-pair observed">
          <span>Observed</span>
          <strong>{esc(observed)}</strong>
        </div>
      </div>
    </div>
  );
}

export function ExpectedCard({
  refOut,
  out,
}: {
  refOut: Record<string, unknown>;
  out: Record<string, unknown>;
}) {
  const hasOutputs = Array.isArray(refOut.expected_outputs) && refOut.expected_outputs.length > 0;
  const hasActions = Array.isArray(refOut.expected_actions) && refOut.expected_actions.length > 0;
  const answer = String(out.final_answer ?? "").toLowerCase();
  const actualTools = (Array.isArray(out.tool_calls) ? out.tool_calls : []).map((t) =>
    String(typeof t === "string" ? t : (t as { name?: string })?.name ?? "").toLowerCase(),
  );

  if (!hasOutputs && !hasActions) return null;

  return (
    <div className="card sample-brief-card expected-card">
      <div className="run-title section-title">
        <div className="run-title-main">Expected</div>
      </div>
      {hasOutputs ? (
        <>
          <div className="expected-label">Answer checks</div>
          <div className="expected-checks">
            {(refOut.expected_outputs as unknown[]).map((o, i) => {
              const ok = answer.includes(String(o).toLowerCase());
              return (
                <ExpectedCheckRow
                  key={i}
                  ok={ok}
                  expected={String(o)}
                  observed={ok ? answerSnippet(out.final_answer, o) : "not found in answer"}
                />
              );
            })}
          </div>
        </>
      ) : null}
      {hasActions ? (
        <>
          <div className="expected-label">Action checks</div>
          <div className="expected-checks">
            {(refOut.expected_actions as { name?: string; arguments?: unknown }[]).map((a, i) => {
              const name = String(a.name ?? "?");
              const ok = actualTools.includes(name.toLowerCase());
              return (
                <ExpectedCheckRow
                  key={i}
                  ok={ok}
                  expected={name}
                  detail={a.arguments ? pretty(a.arguments) : ""}
                  observed={ok ? `called ${name}` : "not observed in tool calls"}
                />
              );
            })}
          </div>
        </>
      ) : null}
    </div>
  );
}
