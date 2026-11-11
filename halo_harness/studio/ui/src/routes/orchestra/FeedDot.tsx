// The live feed's dot (the status bar): green connected, amber connecting or reconnecting, red unreachable; it ticks
// once per event. 3.4.0.0 D: the Live feed and Sessions panels of the old console left long ago; the dot stays.
import { studio, useStore, type FeedStatus } from "../../lib/store";
import { useStateMotion } from "../../lib/motion";

const STATUS_TEXT: Record<FeedStatus, string> = {
  off: "off",
  connecting: "connecting",
  open: "connected",
  retrying: "reconnecting",
  down: "unreachable",
};

export function FeedDot() {
  const status = useStore(studio, (s) => s.feed.status);
  const events = useStore(studio, (s) => s.feed.events);
  const motion = useStateMotion(status === "open" ? "live" : status === "down" ? "error" : status === "off" ? "none" : "waiting", events);
  return <span className="feed-dot" data-status={status} {...motion} aria-label={`live feed ${STATUS_TEXT[status]}`} />;
}
