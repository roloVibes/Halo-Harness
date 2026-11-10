// The status bar (a HudStrip): the live feed dot (green connected, amber
// connecting or reconnecting, red unreachable; it ticks once per event), the
// session and event counts, the section's own status line (3.0.7.0: Roles
// and Design set theirs from their stores: the lineup and its problems,
// the project), the section
// and its layout, and the keys. The FLEET cell counts the agents at work and
// the decisions waiting in the Fleet attention queue, in every section;
// 3.0.6.0 R8: and the fleet missions running now. 3.1.6.0 R6: the section keys' hint reads the registry's first and
// last key. 3.3.16.0 R1: the TEAM cell went with Team's board (a team run's gate still shows in Fleet: Attention);
// in Agents the layout and the status line are the view's own workspace's (Cast's Roles, Runs' Orchestra).
import { HudCell, HudStrip, Kbd } from "../lib/ui";
import { studio, useStore } from "../lib/store";
import { layoutStore } from "../lib/workspace/persist";
import { FeedDot } from "../routes/orchestra/FeedPanels";
import { SECTIONS, useSectionDef } from "../routes";
import { useAttnCount } from "../routes/fleet/pstore";
import { useRunningMissions } from "../routes/fleet/Mission";
import { useCounts } from "../routes/fleet/store";
import { startFleet } from "../routes/fleet/sync";
import { useEffect } from "react";

const FEED_TEXT = { off: "feed off", connecting: "connecting", open: "live", retrying: "reconnecting", down: "feed down" } as const;

export function StatusBar() {
  const feed = useStore(studio, (s) => s.feed);
  const section = useStore(studio, (s) => s.section);
  const def = useSectionDef(section); // 3.3.16.0 R1: Agents' is the workspace it draws now (roles or orchestra)
  const custom = useStore(layoutStore(def.id), (s) => s.custom);
  const line = useStore(studio, (s) => s.status[def.id] || s.status[section]);
  const title = def.title;
  const paged = !!def.paged; // 3.3.1.0 R1: Setup has pages, not a layout
  useEffect(() => startFleet(), []); // the fleet counts in every section, rail open or not
  const fleet = useCounts();
  const attn = useAttnCount(fleet.attention);
  const running = useRunningMissions();
  return (
    <HudStrip label="Status">
      <HudCell title="The live feed from every running halo session (/api/events)">
        <span className="feed-cell" data-status={feed.status}>
          <FeedDot />
          <span className="mono">{FEED_TEXT[feed.status]}</span>
        </span>
      </HudCell>
      <HudCell label="SESSIONS">
        <span className="mono">{feed.sessions.length}</span>
      </HudCell>
      <HudCell label="FLEET" title="Agents at work in every connected harness, the missions running and how many decisions wait on you (Fleet: Attention)">
        <span className="mono" data-testid="status-fleet">
          {fleet.live} live
          {running > 0 && <span data-testid="status-missions"> · {running} mission{running === 1 ? "" : "s"}</span>}
          {attn > 0 && <b className="fr-attn" data-testid="status-attention"> · {attn} need{attn === 1 ? "s" : ""} you</b>}
        </span>
      </HudCell>
      <HudCell label="EVENTS">
        <span className="mono">
          {feed.events}
          {feed.lastKind ? ` · ${feed.lastKind}` : ""}
        </span>
      </HudCell>
      {line && (
        <HudCell label={title.toUpperCase()} grow title={line}>
          <span className="mono section-status" data-testid="section-status">
            {line}
          </span>
        </HudCell>
      )}
      <HudCell label="VIEW" grow={!line}>
        <span className="mono">
          {title.toLowerCase()} · {paged ? "one page at a time" : `layout ${custom ? "yours" : "default"}`}
        </span>
      </HudCell>
      <HudCell>
        <span className="hud-keys">
          <Kbd keys="?" /> how it works <Kbd keys="Mod+K" /> commands <Kbd keys={SECTIONS[0].kbd} />-<Kbd keys={SECTIONS[SECTIONS.length - 1].kbd} /> sections <Kbd keys="Esc" /> close
        </span>
      </HudCell>
    </HudStrip>
  );
}
