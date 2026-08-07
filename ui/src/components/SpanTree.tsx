import { useState } from "react";
import type { SpanNode } from "../api/types";
import { esc, pretty } from "../utils/format";
import {
  INDENT,
  attrValue,
  buildTree,
  collectMessages,
  displaySpanKind,
  expandCompactTraceSpans,
  fmtMs,
  isTraceRootNode,
  kindColor,
  kindSummary,
  normalizeVisibleSpans,
  spanId,
  tokenTotal,
  toTime,
  trunc,
  type TreeNode,
} from "../utils/spanTree";

function SpanDetail({ span }: { span: SpanNode }) {
  const a = span.attributes ?? {};
  const kind = String(span.span_kind || "").toLowerCase();
  const inMsgs = collectMessages(a, "llm.input_messages");
  const outMsgs = collectMessages(a, "llm.output_messages");
  const inp = attrValue(a, "input.value") ?? attrValue(a, "input");
  const outp = attrValue(a, "output.value") ?? attrValue(a, "output");

  return (
    <div>
      {kind === "llm" && inMsgs.length ? (
        <div className="detail-sec">
          <p className="card-label">Input messages</p>
          {inMsgs.map((m, i) => (
            <div key={i} className="msg">
              <div className="msg-role">{esc(m.role || "message")}</div>
              <div className="msg-content">{esc(trunc(String(m.content ?? pretty(m))))}</div>
            </div>
          ))}
        </div>
      ) : null}
      {kind === "llm" && outMsgs.length ? (
        <div className="detail-sec">
          <p className="card-label">Output messages</p>
          {outMsgs.map((m, i) => (
            <div key={i} className="msg">
              <div className="msg-role">{esc(m.role || "message")}</div>
              <div className="msg-content">{esc(trunc(String(m.content ?? pretty(m))))}</div>
            </div>
          ))}
        </div>
      ) : null}
      {!(kind === "llm" && (inMsgs.length || outMsgs.length)) ? (
        <>
          {inp != null ? (
            <div className="detail-sec">
              <p className="card-label">Input</p>
              <pre className="json">{esc(trunc(pretty(inp)))}</pre>
            </div>
          ) : null}
          {outp != null ? (
            <div className="detail-sec">
              <p className="card-label">Output</p>
              <pre className="json">{esc(trunc(pretty(outp)))}</pre>
            </div>
          ) : null}
        </>
      ) : null}
      <div className="detail-sec">
        <details className="raw">
          <summary>All attributes</summary>
          <pre className="json">{esc(pretty(a))}</pre>
        </details>
      </div>
    </div>
  );
}

function TraceNodeRow({
  node,
  level,
  t0,
  total,
  open,
  onToggle,
  kidsCollapsed,
  onToggleKids,
}: {
  node: TreeNode;
  level: number;
  t0: number;
  total: number;
  open: boolean;
  onToggle: () => void;
  kidsCollapsed: boolean;
  onToggleKids: () => void;
}) {
  const s = node.span;
  const durMs = Math.max(0, node.rangeEnd - node.rangeStart);
  const offPct = ((node.rangeStart - t0) / total) * 100;
  const widPct = Math.max(1.5, (durMs / total) * 100);
  const kind = displaySpanKind(s);
  const color = kindColor(kind);
  const isErr = String(s.status_code).toUpperCase() === "ERROR";
  const hasKids = node.children.length > 0;
  const tokens = tokenTotal(s.attributes ?? {});

  return (
    <>
      <div
        className={`trace-node${open ? " sel" : ""}`}
        style={{ ["--kind-color" as string]: color, marginLeft: level * INDENT }}
        onClick={onToggle}
        role="button"
        tabIndex={0}
        onKeyDown={(e) => {
          if (e.key === "Enter" || e.key === " ") {
            e.preventDefault();
            onToggle();
          }
        }}
      >
        <div className="trace-node-rail">
          <span className="trace-node-dot" />
        </div>
        <div className="trace-node-body">
          <div className="trace-node-top">
            {kind !== "UNKNOWN" ? <span className="trace-kind">{kind}</span> : null}
            <span className="trace-node-name">{s.name || "span"}</span>
          </div>
        </div>
        <div className="trace-node-time">
          <div className="trace-time-meta">
            <span className="trace-node-meta">
              {fmtMs(durMs)}
              {tokens ? ` · ${tokens} tok` : ""}
            </span>
            {isErr ? <span className="trace-status err">ERROR</span> : null}
            {!isErr && String(s.status_code).toUpperCase() === "OK" ? (
              <span className="trace-status ok">OK</span>
            ) : null}
          </div>
          <div className="trace-mini-track">
            <div className="bar" style={{ left: `${offPct}%`, width: `${widPct}%`, background: color }} />
          </div>
        </div>
        <button
          type="button"
          className={`trace-twist${hasKids ? "" : " hidden"}${kidsCollapsed ? " collapsed" : ""}`}
          onClick={(e) => {
            e.stopPropagation();
            onToggleKids();
          }}
        >
          ▾
        </button>
      </div>
      {open ? (
        <div className="node-detail" style={{ ["--detail-indent" as string]: `${level * INDENT}px` }}>
          <SpanDetail span={s} />
        </div>
      ) : null}
    </>
  );
}

function TreeItem({
  node,
  level,
  t0,
  total,
  isLast,
}: {
  node: TreeNode;
  level: number;
  t0: number;
  total: number;
  isLast: boolean;
}) {
  const [open, setOpen] = useState(false);
  const [kidsCollapsed, setKidsCollapsed] = useState(false);
  const hasKids = node.children.length > 0;

  return (
    <li
      className={`trace-flow-item ${level ? "child" : "root"} ${isTraceRootNode(node) ? "flow-root" : ""} ${isLast ? "last" : ""}`}
      style={{ ["--level" as string]: level }}
    >
      {level > 0 ? (
        <>
          <span
            className="trace-edge"
            style={{ left: (level - 1) * INDENT + 11, width: INDENT }}
          />
          {!isLast ? (
            <span className="trace-edge-cont" style={{ left: (level - 1) * INDENT + 11 }} />
          ) : null}
        </>
      ) : null}
      <TraceNodeRow
        node={node}
        level={level}
        t0={t0}
        total={total}
        open={open}
        onToggle={() => setOpen(!open)}
        kidsCollapsed={kidsCollapsed}
        onToggleKids={() => setKidsCollapsed(!kidsCollapsed)}
      />
      {hasKids ? (
        <ul className={`node-kids trace-flow-kids${kidsCollapsed ? " collapsed" : ""}`}>
          {node.children.map((c, i) => (
            <TreeItem
              key={spanId(c.span, i)}
              node={c}
              level={level + 1}
              t0={t0}
              total={total}
              isLast={i === node.children.length - 1}
            />
          ))}
        </ul>
      ) : null}
    </li>
  );
}

function GlobalTraceAxis({ spans, t0, total }: { spans: SpanNode[]; t0: number; total: number }) {
  const timed = spans
    .map((span, i) => {
      const start = toTime(span.start_time);
      const end = Math.max(start, toTime(span.end_time));
      return { span, id: spanId(span, i), start, end };
    })
    .filter((item) => item.end >= item.start && item.end - t0 >= 0)
    .sort((a, b) => a.start - b.start);

  return (
    <div className="trace-global-axis" aria-label="Full trace execution timeline">
      <div className="trace-global-meta">
        <span>0ms</span>
        <span>{fmtMs(total)}</span>
      </div>
      <div className="trace-global-track">
        {timed.map((item) => {
          const kind = displaySpanKind(item.span);
          const left = Math.max(0, Math.min(100, ((item.start - t0) / total) * 100));
          const right = Math.max(left, Math.min(100, ((item.end - t0) / total) * 100));
          const width = Math.max(0.35, right - left);
          return (
            <span
              key={item.id}
              className="trace-global-seg"
              title={`${kind !== "UNKNOWN" ? `${kind} · ` : ""}${item.span.name || "span"} · ${fmtMs(item.end - item.start)}`}
              style={{
                left: `${left}%`,
                width: `${width}%`,
                background: kindColor(kind),
              }}
            />
          );
        })}
      </div>
    </div>
  );
}

export function SpanTree({ spans }: { spans: SpanNode[] }) {
  const realVisible = normalizeVisibleSpans(spans, { filterInternal: false });
  const expanded = expandCompactTraceSpans(spans);
  const visible = normalizeVisibleSpans(expanded, { filterInternal: false });
  if (!realVisible.length) return <p className="muted">No trace available</p>;
  const { roots, t0, total } = buildTree(visible);
  const syntheticCount = Math.max(0, visible.length - realVisible.length);
  const summary = kindSummary(realVisible);
  return (
    <div className="trace-flow">
      <div className="trace-flow-head">
        <div className="trace-flow-title">Agent Run</div>
        <div className="trace-flow-sub">
          {realVisible.length} spans{syntheticCount ? ` · ${syntheticCount} message nodes` : ""} · total {fmtMs(total)}
          {summary ? ` · ${summary}` : ""}
        </div>
      </div>
      <GlobalTraceAxis spans={realVisible} t0={t0} total={total} />
      <ul className="trace-flow-list">
        {roots.map((n, i) => (
          <TreeItem
            key={spanId(n.span, i)}
            node={n}
            level={0}
            t0={t0}
            total={total}
            isLast={i === roots.length - 1}
          />
        ))}
      </ul>
    </div>
  );
}
