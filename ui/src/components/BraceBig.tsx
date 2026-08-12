import type { CSSProperties } from "react";
import { esc } from "../utils/format";

const PATHS = {
  left: "M27 1 C16 1 21 9 19 24 C17 40 15 46 4 50 C15 54 17 60 19 76 C21 91 16 99 27 99",
  right: "M3 1 C14 1 9 9 11 24 C13 40 15 46 26 50 C15 54 13 60 11 76 C9 91 14 99 3 99",
};

interface Props {
  side: "left" | "right";
  l1: string;
  l2: string;
  onClick: () => void;
  style?: CSSProperties;
}

export function BraceBig({ side, l1, l2, onClick, style }: Props) {
  const label = (
    <div className="brace-label">
      <div className="brace-l1">{esc(l1)}</div>
      <div className="brace-l2">{esc(l2)}</div>
    </div>
  );
  const svg = (
    <svg viewBox="0 0 30 100" preserveAspectRatio="none">
      <path
        d={PATHS[side]}
        fill="none"
        stroke="currentColor"
        strokeWidth="2"
        strokeLinecap="round"
        vectorEffect="non-scaling-stroke"
      />
    </svg>
  );
  return (
    <div className={`sbrace ${side}`} style={style} onClick={onClick} role="button" tabIndex={0}>
      {side === "left" ? (
        <>
          {label}
          {svg}
        </>
      ) : (
        <>
          {svg}
          {label}
        </>
      )}
    </div>
  );
}
