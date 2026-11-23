// Last said in the step-in sheet's body (3.6.0.14 O1-6): ONE `GET sessions/{sid}/agents/{aid}/tail?n=20&kinds=...` at
// the click, a snapshot (choosing another row later reads nothing again). The sheet opens when it answers or at 1 s
// (sheetPlace.ts saidOpen); answered later, "Reading what it said..." stays where it was and the answer goes to the
// body's end (truthBits.ts saidParts). A done helper's last words come back as `handback`: they are what it said. When
// the sheet goes, the timer is cleared, the request aborted (quietly: lib/apiLimit.ts DROPPED) and its answer dropped.
// The request and its timer live here only.
import { useEffect, useState } from "react";
import { api } from "../../../lib/api";
import { SAID_WAIT_MS, saidOpen } from "./sheetPlace";
import type { Target } from "./stepInTarget";
import type { Said } from "./truthBits";

type Tail = { events?: { kind?: string; text?: string; ts?: number }[] };

/** The agent the sheet reads and its name as its row shows it (3.6.0.15 F8: the block names whose words it shows): the
 *  chosen row's at the click, else a member's own, else main's; null: nothing to read. */
export function saidWho(t: Target): { aid: string; name: string } | null {
  if (t.who[0]?.aid) return { aid: t.who[0].aid, name: t.who[0].name };
  if (t.id.startsWith("member:")) {
    const aid = t.id.slice("member:".length);
    return { aid, name: t.who.find((w) => w.aid === aid)?.name || t.title };
  }
  return t.id === "box:main" ? { aid: "main", name: t.who[0]?.name || "main" } : null;
}

/** `got`: null (nothing to read), "reading", the answer (with the name read at the click) or its error; `ready`: the
 *  sheet may open. */
export function useSaid(sid: string, who: { aid: string; name: string } | null): { got: Said | null; ready: boolean } {
  const aid = who?.aid || null;
  const [got, setGot] = useState<Said | null>(aid ? "reading" : null);
  const [waited, setWaited] = useState(0);
  useEffect(() => { // once, at the click
    if (!aid) return;
    let dropped = false;
    const ctl = new AbortController();
    const timer = setTimeout(() => setWaited(SAID_WAIT_MS), SAID_WAIT_MS);
    api.get<Tail>(`sessions/${encodeURIComponent(sid)}/agents/${encodeURIComponent(aid)}/tail`, { n: 20, kinds: "text,thinking,handback" }, ctl.signal)
      .then((r) => dropped || setGot({ events: r?.events || [], who: who?.name }), (e) => dropped || setGot({ error: e instanceof Error ? e.message : String(e) }))
      .finally(() => clearTimeout(timer));
    return () => { dropped = true; clearTimeout(timer); ctl.abort(); };
  }, []); // eslint-disable-line react-hooks/exhaustive-deps
  return { got, ready: !aid || saidOpen(got !== "reading", waited) };
}

/** Its lines: the said line, then (after a cut text) where the rest is; `late`: the answer that came after the open. */
export function StepInSaid({ lines, late }: { lines: string[]; late?: boolean }) {
  if (!lines.length) return null;
  return (
    <div className="mp-step-in-said" data-testid="map-step-in-said" data-late={late || undefined}>
      <p className="mp-step-in-said-text mono">{lines[0]}</p>
      {lines[1] && <p className="mp-step-in-state mono" data-testid="map-step-in-said-rest">{lines[1]}</p>}
    </div>
  );
}
