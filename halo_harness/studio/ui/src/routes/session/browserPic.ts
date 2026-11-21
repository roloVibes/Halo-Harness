// 3.6.0.6 W (the owner: "FULLY CONTROL A BROWSER AND SEE IT"): which page picture a Browser step's detail shows.
// A step that changed the page ends its result with "Picture: <path>" (tools/browser.py); a screenshot names its own;
// the session log's entry carries it as `picture` (agent_transcript._picture: a long page cuts it off the text). A
// step with none of its own (read, close) shows the newest picture of a Browser step before it, of the same agent.
import type { LiveLine } from "../shared/liveTypes";

const IN_TEXT = /(?:^Picture: |Screenshot saved at |"path": ")([^\n"]*?page-\d+\.png)/m;
const BARE = /^[^\n]*page-\d+\.png$/;

/** The picture's path in `text` (a result, or a bare path), or "". */
export function picIn(text: string): string {
  const t = String(text || "").trim();
  if (BARE.test(t)) return t;
  return IN_TEXT.exec(t)?.[1] || "";
}

/** The picture line `x` (at `j` in `lines`) shows once its result `text` lands: its own, else the newest before it. */
export function picOf(lines: LiveLine[], j: number, x: LiveLine, text: string): string {
  if (x.tool !== "Browser") return "";
  const own = picIn(text);
  if (own) return own;
  for (let i = j - 1; i >= 0; i--) {
    const y = lines[i];
    if (y.key === x.key && y.kind === "tool" && y.tool === "Browser" && y.pic) return y.pic;
  }
  return "";
}

/** The route that serves it: the session's own attachments folder (`<halo home>/attachments/<session>/<name>`). */
export function picRoute(path: string): string {
  const parts = String(path || "").split(/[\\/]+/).filter(Boolean);
  const name = parts[parts.length - 1] || "";
  const sid = parts[parts.length - 2] || "";
  return `api/sessions/${encodeURIComponent(sid)}/attachments/${encodeURIComponent(name)}`;
}
