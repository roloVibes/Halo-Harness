// 3.3.2.0 R1 "the icon rail": the sections as the rail's first block, one
// button per section (the eight core ones, then the packs' own under a thin
// divider with the diamond), an icon each and the title as its tooltip and
// accessible name; the label shows only while the rail is expanded. The
// current one is lit; Session carries a dot while a session is live here,
// Fleet the number of agents at work (the Fleet tree's count, which used to
// take a strip of the rail). A row prints no shortcut: Alt+N lives in
// shell/keys.ts, the palette's Go to hints and the ? help (the row keeps it as
// `data-kbd` for the drivers, never drawn). The buttons are a
// vertical tablist and keep `data-testid="section-tab"` (they replaced the
// header's tab strip), so `[data-testid=section-tab][aria-selected=true]`
// is still the current section.
import { useEffect } from "react";
import { Icon } from "../lib/ui";
import { goSection, studio, useStore, type SectionId } from "../lib/store";
import { useRecent } from "../lib/motion";
import { useSections, type SectionDef } from "../routes";
import { useCounts } from "../routes/fleet/store";
import { startFleet } from "../routes/fleet/sync";

const ICONS: Record<string, string> = {
  session: "session", team: "team", roles: "roles", fleet: "fleet", design: "design", orchestra: "orchestra", packs: "packs", setup: "setup",
};

/** The sections that ran something in the last few seconds (the old tab strip's "working" breath). */
function useBusy(): Partial<Record<SectionId, boolean>> {
  const activity = useStore(studio, (s) => s.activity);
  const orchestra = useRecent(activity.orchestra, 3000);
  const fleet = useRecent(activity.fleet, 3000);
  const team = useRecent(activity.team, 3000);
  return { orchestra, fleet, team, session: fleet };
}

function Item({ s, on, busy, pack }: { s: SectionDef; on: boolean; busy: boolean; pack: boolean }) {
  const live = useStore(studio, (st) => st.feed.sessions.length);
  const fleet = useCounts().live;
  return (
    <button
      role="tab"
      aria-selected={on}
      className={"rail-item rail-section" + (on ? " on" : "") + (pack ? " rail-pack" : "")}
      data-tab-id={s.id}
      data-testid="section-tab"
      data-pack={pack || undefined}
      data-kbd={s.kbd || undefined}
      data-motion={busy && !on ? "working" : "none"}
      title={s.title}
      aria-label={s.title}
      onClick={() => goSection(s.id)}
    >
      <span className="rail-icon">
        <Icon name={ICONS[s.id] ?? "diamond"} />
        {s.id === "session" && live > 0 && <span className="rail-live-dot" data-testid="rail-live" aria-hidden="true" />}
        {s.id === "fleet" && fleet > 0 && <span className="rail-count mono" data-testid="rail-fleet-count" data-count={fleet} aria-hidden="true" />}
      </span>
      <span className="tab-label rail-item-text">{s.title}</span>
    </button>
  );
}

export function RailSections() {
  useEffect(() => startFleet(), []); // the live count on the Fleet icon, in every section
  const section = useStore(studio, (s) => s.section);
  const all = useSections();
  const busy = useBusy();
  const core = all.filter((s) => !s.id.includes("--"));
  const packs = all.filter((s) => s.id.includes("--"));
  return (
    <div className="rail-sections" role="tablist" aria-orientation="vertical" aria-label="Sections" data-testid="rail-sections">
      {core.map((s) => (
        <Item key={s.id} s={s} on={s.id === section} busy={!!busy[s.id]} pack={false} />
      ))}
      {packs.length > 0 && <span className="rail-divider" data-testid="rail-packs" role="separator" aria-label="Packs" />}
      {packs.map((s) => (
        <Item key={s.id} s={s} on={s.id === section} busy={false} pack />
      ))}
    </div>
  );
}
