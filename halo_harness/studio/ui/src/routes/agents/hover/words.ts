// Small words the hover cards share (3.3.16.1): what a model takes in plain words, how long ago, for how long, a count
// with its noun. A fact that is not known is "" (the card leaves its row out).
// files, web: 3.3.17.0 cp:work (your work's Copilot reads OneDrive/SharePoint files and the web)
const TAKE_WORD: Record<string, string> = { vision: "images", audio: "audio", video: "video", pdf: "PDFs", files: "files", web: "web", image: "makes images", tools: "tools", think: "think" };
const ORDER = ["vision", "audio", "video", "pdf", "files", "web", "image", "tools", "think"];

/** "text, images, tools, think" from a model row's takes (3.3.15.0 R2); "" when the catalog states nothing. */
export function takesWords(takes: string[] | null | undefined): string {
  if (!takes?.length || takes.includes("?")) return "";
  return ["text", ...ORDER.filter((t) => takes.includes(t)).map((t) => TAKE_WORD[t])].join(", ");
}

/** "12s", "4m 05s", "2h 10m", "3d" for a number of seconds. */
export function span(s: number): string {
  const v = Math.max(0, Math.round(s));
  if (v < 60) return `${v}s`;
  if (v < 3600) return `${Math.floor(v / 60)}m ${String(v % 60).padStart(2, "0")}s`;
  if (v < 86400) return `${Math.floor(v / 3600)}h ${Math.floor((v % 3600) / 60)}m`;
  return `${Math.floor(v / 86400)}d`;
}

/** Seconds since an epoch (in seconds, or ms when it is that large); null when there is none. */
export function since(at: number | null | undefined, now = Date.now()): number | null {
  const t = Number(at) || 0;
  if (!t) return null;
  return Math.max(0, (now - (t > 1e12 ? t : t * 1000)) / 1000);
}

/** "3m 05s ago" or "". */
export function ago(at: number | null | undefined, now = Date.now()): string {
  const s = since(at, now);
  return s == null ? "" : `${span(s)} ago`;
}

export const plural = (n: number, one: string, many = one + "s"): string => `${n} ${n === 1 ? one : many}`;

/** "$0.0123", or "" when nothing was spent or nothing is known. */
export function spent(usd: number | null | undefined): string {
  const v = Number(usd);
  if (!Number.isFinite(v) || v <= 0) return "";
  return v >= 1 ? `$${v.toFixed(2)}` : `$${v.toFixed(4)}`;
}

/** "1.2k in / 340 out" from token counts ("" when neither is known). */
export function tokens(inp: number | null | undefined, out: number | null | undefined): string {
  const f = (v: number) => (v >= 10000 ? `${Math.round(v / 1000)}k` : v >= 1000 ? `${(v / 1000).toFixed(1)}k` : String(v));
  const a = Number(inp) || 0, b = Number(out) || 0;
  return a || b ? `${f(a)} in / ${f(b)} out` : "";
}

export const joined = (parts: (string | false | null | undefined)[], sep = " · "): string => parts.filter(Boolean).join(sep);
