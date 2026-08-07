export function esc(s: unknown): string {
  return String(s ?? "").replace(/[&<>"]/g, (c) => ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;" })[c] as string);
}

export function pretty(v: unknown): string {
  try {
    return typeof v === "string" ? v : JSON.stringify(v, null, 2);
  } catch {
    return String(v);
  }
}

export function avgNumber(xs: (number | undefined | null)[]): number | null {
  const nums = xs.filter((x): x is number => typeof x === "number");
  return nums.length ? nums.reduce((s, x) => s + x, 0) / nums.length : null;
}
