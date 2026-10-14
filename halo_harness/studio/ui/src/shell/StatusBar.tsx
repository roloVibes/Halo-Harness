// The status bar (a HudStrip): the live feed dot (green connected, amber
// connecting or reconnecting, red unreachable; it ticks once per event), the
// session and event counts, the section and its layout, and the keys.
import { HudCell, HudStrip, Kbd } from "../lib/ui";
import { studio, useStore } from "../lib/store";
import { layoutStore } from "../lib/workspace/persist";
import { FeedDot } from "../routes/orchestra/FeedPanels";
import { sectionDef } from "../routes";

const FEED_TEXT = { off: "feed off", connecting: "connecting", open: "live", retrying: "reconnecting", down: "feed down" } as const;

export function StatusBar() {
  const feed = useStore(studio, (s) => s.feed);
  const section = useStore(studio, (s) => s.section);
  const custom = useStore(layoutStore(section), (s) => s.custom);
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
      <HudCell label="EVENTS">
        <span className="mono">
          {feed.events}
          {feed.lastKind ? ` · ${feed.lastKind}` : ""}
        </span>
      </HudCell>
      <HudCell label="VIEW" grow>
        <span className="mono">
          {sectionDef(section).title.toLowerCase()} · layout {custom ? "yours" : "default"}
        </span>
      </HudCell>
      <HudCell>
        <span className="hud-keys">
          <Kbd keys="Mod+K" /> commands <Kbd keys="Alt+1" />-<Kbd keys="Alt+5" /> sections <Kbd keys="Esc" /> close
        </span>
      </HudCell>
    </HudStrip>
  );
}
