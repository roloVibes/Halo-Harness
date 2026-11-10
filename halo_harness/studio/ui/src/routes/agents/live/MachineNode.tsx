// A machine on Agents -> Live's fleet scope (3.3.16.0 R2 "the Fleet fold": a machine's agents in Agents; the Fleet
// Map's harness box and its Tree panel's harness row before): its box around everything that runs on it (`fleet-box`,
// `data-key="h:<id>"`: a dragged mission part is dropped into it) and its head node -- the presence dot (live / idle /
// away, People's rule), the name, host and Halo version (amber chip when it differs: `halo update`), its sessions and
// the agents live, what it spent today, its capability chips (at most three, the catalog's). A click puts the machine
// in the inspector (its summary); the box lights while "Who can..." picked it.
import type { KeyboardEvent } from "react";
import { cost, short } from "../../orchestra/format";
import { useCaps } from "../../fleet/caps";
import { presence } from "../../fleet/People";
import { isLive, useFleet } from "../../fleet/store";
import type { LiveBox, LiveGroup } from "../../roles/liveLayout";

/** The machine's box; `label` (Session's Map, where no machine node is drawn) names it in its corner. */
export function MachineBox({ g, label = false }: { g: LiveGroup; label?: boolean }) {
  const h = useFleet((s) => s.harnesses.find((x) => x.id === g.card));
  const who = useCaps((s) => s.focus === g.card && !!s.focus);
  return (
    <div className="rlm-machine-box" style={{ left: g.x, top: g.y, width: g.w, height: g.h }} data-testid="fleet-box" data-key={`h:${g.card}`}
         data-online={(h && (h.local || h.online)) || undefined} data-local={h?.local || undefined} data-who={who || undefined} aria-hidden="true">
      {label && <span className="rlm-box-label mono">{h?.name || g.card.slice(0, 8)}</span>}
    </div>
  );
}

export function MachineNode({ b, now, selected, onPick }: { b: LiveBox; now: number; selected: boolean; onPick: (hid: string) => void }) {
  const hid = b.node.harness || "";
  const h = useFleet((s) => s.harnesses.find((x) => x.id === hid));
  const chips = useCaps((s) => s.rows?.find((r) => r.harness === hid)?.chips) || [];
  if (!h) return null;
  const p = presence(h, now);
  const sessions = (h.sessions || []).length;
  const live = (h.sessions || []).reduce((n, s) => n + (s.agents || []).filter(isLive).length, 0);
  const pick = () => onPick(hid);
  const onKey = (e: KeyboardEvent<HTMLDivElement>) => (e.key === "Enter" || e.key === " ") && (e.preventDefault(), pick());
  return (
    <div className="rlm-node rlm-machine" style={{ left: b.x, top: b.y, width: b.w, height: b.h }} role="button" tabIndex={0} onClick={pick} onKeyDown={onKey}
         data-testid="live-machine" data-harness={hid} data-presence={p} data-local={h.local || undefined} data-selected={selected || undefined}
         aria-label={`${h.name || hid}: ${h.local ? "this halo" : p}`} title={[h.name, h.host, h.version, h.local ? "this halo" : p].filter(Boolean).join(" · ")}>
      <div className="rlm-head">
        <span className="fpe-dot" data-presence={p} aria-hidden="true" />
        <b className="rlm-name">{short(h.name || hid.slice(0, 8), 20)}</b>
        <span className="spacer" />
        {h.version && (
          <span className="og-chip mono" data-mismatch={h.version_mismatch || undefined} data-testid="live-machine-version"
                title={h.version_mismatch ? "another Halo version: run `halo update` on the older one" : "Halo version"}>{h.version}</span>
        )}
      </div>
      <div className="mono muted rlm-line">{h.local ? "this halo" : p} · {short(h.host || "", 18)} · {cost(h.cost_today)} today</div>
      <div className="mono muted rlm-line" data-testid="live-machine-count">
        {sessions} session{sessions === 1 ? "" : "s"} · {live} live
        {chips.slice(0, 3).map((c) => (
          <span key={c} className="og-chip mono rlm-chip" data-testid="fleet-box-chip">{c.slice(0, 14)}</span>
        ))}
      </div>
    </div>
  );
}
