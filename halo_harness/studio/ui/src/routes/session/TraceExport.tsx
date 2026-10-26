// Export (3.3.0.0 R6, the owner: "have an export button that saves it as an
// .md file, like a tracer file so we can save detailed logs of sessions"):
// on the Live column's header and on its timeline strip. It reads the chosen
// session's trace from `GET sessions/<sid>/trace.md` (session_trace.py: the
// header with the totals, then one entry per row, keys masked, home paths as
// ~ -- the same bytes as `halo session export <sid>` and `/export`) and the
// browser saves it as `halo-trace-<session id>-<yyyy-mm-dd-hhmm>.md`.
import { useState } from "react";
import { token } from "../../lib/api";
import { toast } from "../../lib/store";
import { Button, Icon } from "../../lib/ui";
import { useStripScope } from "./steer";

const pad = (n: number) => String(n).padStart(2, "0");

/** halo-trace-<sid>-<yyyy-mm-dd-hhmm>.md, in the browser's local time. */
export function traceName(sid: string, at = new Date()): string {
  return `halo-trace-${sid}-${at.getFullYear()}-${pad(at.getMonth() + 1)}-${pad(at.getDate())}-${pad(at.getHours())}${pad(at.getMinutes())}.md`;
}

/** Fetch the trace (the route wants the token header) and save it from a Blob. */
export async function exportTrace(sid: string): Promise<boolean> {
  const name = traceName(sid);
  try {
    const res = await fetch(new URL(`api/sessions/${encodeURIComponent(sid)}/trace.md`, location.origin + "/"), {
      headers: { Authorization: "Bearer " + token() },
    });
    const text = await res.text();
    if (!res.ok) throw new Error(`${res.status}: ${text.slice(0, 200)}`);
    const href = URL.createObjectURL(new Blob([text], { type: "text/markdown;charset=utf-8" }));
    const link = document.createElement("a");
    link.href = href;
    link.download = name;
    link.dataset.testid = "trace-link";
    document.body.appendChild(link);
    link.click();
    window.setTimeout(() => (URL.revokeObjectURL(href), link.remove()), 1000);
    toast(`Saved ${name} (${Math.max(1, Math.round(text.length / 1024))} KB): every row of the session, keys masked`, "done", 4000);
    return true;
  } catch (e) {
    toast(`The trace did not download: ${e instanceof Error ? e.message : String(e)}`, "error", 6000);
    return false;
  }
}

export function TraceExport({ where }: { where: "head" | "timeline" }) {
  const sid = useStripScope().session || "";
  const [busy, setBusy] = useState(false);
  const go = async () => {
    setBusy(true);
    await exportTrace(sid);
    setBusy(false);
  };
  return (
    <Button size="sm" variant="ghost" icon={<Icon name="file" />} disabled={!sid || busy} onClick={() => void go()} data-testid="trace-export" data-where={where}
            title={sid ? `Save this session as one Markdown trace: halo-trace-${sid}-<date>.md` : "No session chosen yet"}>
      Export
    </Button>
  );
}
