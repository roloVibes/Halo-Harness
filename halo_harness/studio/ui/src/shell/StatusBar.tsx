// The status bar (a HudStrip): the live feed dot (green connected, amber
// connecting or reconnecting, red unreachable; it ticks once per event), the
// session and event counts, the framed classic page's own status line (Roles,
// Org, Design: the lineup's problems, the company, the project), the section
// and its layout, and the keys.
import { HudCell, HudStrip, Kbd } from "../lib/ui";
import { studio, useStore } from "../lib/store";
import { layoutStore } from "../lib/workspace/persist";
import { FeedDot } from "../routes/orchestra/FeedPanels";
import { sectionDef } from "../routes";
import { useCounts } from "../routes/fleet/store";

const FEED_TEXT = { off: "feed off", connecting: "connecting", open: "live", retrying: "reconnecting", down: "feed down" } as const;

export function StatusBar() {
  const feed = useStore(studio, (s) => s.feed);
  const section = useStore(studio, (s) => s.section);
  const custom = useStore(layoutStore(section), (s) => s.custom);
  const legacy = useStore(studio, (s) => s.legacy[s.section]);
  const title = sectionDef(section).title;
  const fleet = useCounts();
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
      <HudCell label="FLEET" title="Agents at work in every connected harness, and how many wait on you">
        <span className="mono" data-testid="status-fleet">
          {fleet.live} live
          {fleet.attention > 0 && <b className="fr-attn"> · {fleet.attention} need{fleet.attention === 1 ? "s" : ""} you</b>}
        </span>
      </HudCell>
      <HudCell label="EVENTS">
        <span className="mono">
          {feed.events}
          {feed.lastKind ? ` · ${feed.lastKind}` : ""}
        </span>
      </HudCell>
      {legacy && (
        <HudCell label={title.toUpperCase()} grow title={legacy}>
          <span className="mono legacy-status" data-testid="legacy-status">
            {legacy}
          </span>
        </HudCell>
      )}
      <HudCell label="VIEW" grow={!legacy}>
        <span className="mono">
          {title.toLowerCase()} · layout {custom ? "yours" : "default"}
        </span>
      </HudCell>
      <HudCell>
        <span className="hud-keys">
          <Kbd keys="?" /> how it works <Kbd keys="Mod+K" /> commands <Kbd keys="Alt+1" />-<Kbd keys="Alt+6" /> sections <Kbd keys="Esc" /> close
        </span>
      </HudCell>
    </HudStrip>
  );
}
