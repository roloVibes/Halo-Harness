// fleet-people: one row per harness in the fleet: its name and host, its
// Halo version (a chip when it differs from this one's: `halo update` on the
// older one), what it shares and what it lets you do there, what it is on
// (the project and its top session), live / idle / away (from when the hub
// last heard from it), what it has spent today; Message sends its owner a
// note in that session (never the model), Forget (this machine's hub only,
// asks first; Kick before 3.3.16.0 R2) makes it pair again; specs opens its card (3.0.6.0 R6; 3.3.16.0 R2: the
// machine's summary on Agents -> Live, its Specs page). The row is Setup -> Machines' People table and the head of a
// machine's summary on Live.
import { Button, Icon } from "../../lib/ui";
import { cost, short } from "../orchestra/format";
import { projectLabel } from "../agents/live/nodeBits";
import { focusHarness, useCaps } from "./caps";
import { openDialog } from "./pstore";
import { sessionTitle } from "./store";
import type { Harness } from "./types";

const AWAY_S = 120;

export type Presence = "live" | "idle" | "away";

/** live: an agent of it works now; idle: reachable, nothing runs; away: offline or silent for AWAY_S. */
export function presence(h: Harness, now: number): Presence {
  const heard = h.local || (h.online && (!h.last_seen || now / 1000 - h.last_seen < AWAY_S));
  if (!heard) return "away";
  const busy = (h.sessions || []).some((s) => s.busy || s.status === "busy" || (s.agents || []).some((a) => a.state === "running"));
  return busy ? "live" : "idle";
}

/** The session it is most on: a busy one first, else the newest. */
export function topSession(h: Harness) {
  const list = [...(h.sessions || [])];
  list.sort((a, b) => Number(!!b.busy) - Number(!!a.busy) || (Number(b.started) || 0) - (Number(a.started) || 0));
  return list[0] || null;
}

export function Person({ h, now, hubHere }: { h: Harness; now: number; hubHere: boolean }) {
  const p = presence(h, now);
  const top = topSession(h);
  const name = h.name || h.id.slice(0, 8);
  const seen = h.last_seen && !h.local ? `${Math.max(0, Math.round(now / 1000 - h.last_seen))}s ago` : "";
  const capChips = useCaps((s) => s.rows?.find((r) => r.harness === h.id)?.chips);
  return (
    <li className="fpe-row" data-testid="fleet-person" data-id={h.id} data-presence={p}>
      <div className="fpe-top">
        <span className="fpe-dot" data-presence={p} aria-hidden="true" />
        <b className="fpe-name">{name}</b>
        <span className="mono muted fpe-host">{[h.user && h.host ? `${h.user}@${h.host}` : h.host, h.os].filter(Boolean).join(" · ")}</span>
        <span className="spacer" />
        <span className="mono fpe-cost" title="spent today">{cost(h.cost_today)}</span>
      </div>
      <div className="fpe-chips">
        <span className="og-chip mono" data-presence={p} title={seen ? `last heard ${seen}` : undefined}>{h.local ? "this harness" : p}</span>
        {h.version && (
          <span className="og-chip mono" data-mismatch={h.version_mismatch || undefined} title={h.version_mismatch ? "another Halo version: run `halo update` on the older one" : "Halo version"}>
            {h.version}{h.version_mismatch ? " · halo update" : ""}
          </span>
        )}
        {!h.local && <span className="og-chip mono" title="what it shares with this hub">shares {h.share || "?"}</span>}
        {!h.local && <span className="og-chip mono" title="what you may do there">control {h.allow_control || "?"}</span>}
        {(capChips || []).map((c) => <span key={c} className="og-chip mono fcap-chip">{c}</span>)}
        <button className="fpe-specs mono" data-testid="fleet-person-specs" title="what it can do: its spec card (its summary on Agents -> Live)"
                onClick={() => focusHarness(h.id, "fleet-capabilities")}>specs</button>
      </div>
      <div className="fpe-on muted">
        {top ? <>on <b>{short(projectLabel(top), 40)}</b> · {short(sessionTitle(top), 48)}{(h.sessions || []).length > 1 ? ` · +${h.sessions.length - 1} more` : ""}</> : "no session right now"}
      </div>
      {!h.local && (
        <div className="fpe-actions">
          <Button size="sm" icon={<Icon name="send" />} disabled={!top || h.allow_control === "none"} data-testid="fleet-person-message"
                  title={!top ? "no session to send it to" : h.allow_control === "none" ? "it takes no commands from here" : "a note its owner reads in that session (not the model)"}
                  onClick={() => top && openDialog({ kind: "message", hid: h.id, sid: top.session_id, name })}>
            Message
          </Button>
          {hubHere && (
            <Button size="sm" variant="ghost" icon={<Icon name="close" />} onClick={() => openDialog({ kind: "kick", hid: h.id, name })} data-testid="fleet-person-kick" title="it leaves this hub and pairs again with a new code (asks first)">
              Forget
            </Button>
          )}
        </div>
      )}
    </li>
  );
}
