// fleet-people: one row per harness in the fleet: its name and host, its
// Halo version (a chip when it differs from this one's: `halo update` on the
// older one), what it shares and what it lets you do there, what it is on
// (the project and its top session), live / idle / away (from when the hub
// last heard from it), what it has spent today; Message sends its owner a
// note in that session (never the model), Kick (this machine's hub only,
// asks first) makes it pair again. Compact face: who is online.
import { Button, Empty, Icon } from "../../lib/ui";
import type { MotionState } from "../../lib/motion";
import { Metric } from "../orchestra/bits";
import { cost, short } from "../orchestra/format";
import { projectLabel } from "./layout";
import { openDialog } from "./pstore";
import { sessionTitle, useFleet, useNow } from "./store";
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

function Person({ h, now, hubHere }: { h: Harness; now: number; hubHere: boolean }) {
  const p = presence(h, now);
  const top = topSession(h);
  const name = h.name || h.id.slice(0, 8);
  const seen = h.last_seen && !h.local ? `${Math.max(0, Math.round(now / 1000 - h.last_seen))}s ago` : "";
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
            <Button size="sm" variant="ghost" icon={<Icon name="close" />} onClick={() => openDialog({ kind: "kick", hid: h.id, name })} data-testid="fleet-person-kick" title="it leaves this hub (asks first)">
              Kick
            </Button>
          )}
        </div>
      )}
    </li>
  );
}

export function PeopleDetail() {
  const harnesses = useFleet((s) => s.harnesses);
  const hubHere = useFleet((s) => !!s.hub?.serving);
  const loaded = useFleet((s) => s.loaded);
  const now = useNow(true, 5000);
  if (!loaded) return <div className="og-wait mono muted">reading the fleet...</div>;
  if (!harnesses.length) return <Empty title="Nobody here yet" body="This harness shows as soon as Studio reads it; another one joins with a pair code." />;
  return (
    <ul className="fpe" data-testid="fleet-people-list">
      {harnesses.map((h) => <Person key={h.id} h={h} now={now} hubHere={hubHere} />)}
    </ul>
  );
}

export function PeopleGlance() {
  const harnesses = useFleet((s) => s.harnesses);
  const now = useNow(true, 10000);
  const on = harnesses.filter((h) => presence(h, now) !== "away");
  return (
    <div className="glance" data-testid="fleet-people-glance">
      <div className="glance-numbers">
        <Metric value={on.length} label="online" tone={on.length ? "accent" : undefined} />
        <Metric value={harnesses.length} label="harnesses" />
      </div>
      <div className="glance-hint mono">{on.map((h) => h.name || h.id.slice(0, 8)).join(" · ") || "nobody online"}</div>
    </div>
  );
}

export function usePeopleMotion(): MotionState {
  const harnesses = useFleet((s) => s.harnesses);
  const now = useNow(true, 10000);
  return harnesses.some((h) => presence(h, now) === "live") ? "working" : harnesses.length ? "idle" : "none";
}
