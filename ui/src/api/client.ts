export function apiBase(): string {
  const base = window.Config?.basename ?? "";
  return base.endsWith("/") ? base.slice(0, -1) : base;
}

export async function fetchJSON<T>(path: string): Promise<T> {
  const url = `${apiBase()}${path.startsWith("/") ? path : `/${path}`}`;
  const res = await fetch(url, { headers: { accept: "application/json" } });
  const data = (await res.json()) as T & { error?: string };
  if (!res.ok) {
    throw new Error((data as { error?: string }).error || res.statusText);
  }
  return data;
}
