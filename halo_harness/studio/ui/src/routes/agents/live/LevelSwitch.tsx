// The three levels on Live's bar (3.3.18.0 "The living canvas" part 4, levels.ts): far | mid | near, for the keyboard
// and the pointer alike. A choice sets the zoom to that level's (the thing in the middle of the view stays there); the
// zoom itself, by the wheel or - / +, moves the level at its thresholds and this switch follows.
import { LEVEL_ZOOM, unpinLevel, type Level } from "./levels";

const SAYS: Record<Level, string> = {
  far: "Far: blocks only, each with its count, state, cost and what waits",
  mid: "Mid: every agent's box",
  near: "Near: each box grows to show its current thought and its running tool's last output",
};

export function LevelSwitch({ level, zoomAt }: { level: Level; zoomAt: (z: number) => void }) {
  return (
    <span className="segmented lv-levels" role="group" aria-label="What the zoom shows: far, mid or near" data-testid="live-level" data-level={level}>
      {(["far", "mid", "near"] as Level[]).map((l) => (
        <button key={l} className={level === l ? "on" : ""} aria-pressed={level === l} onClick={() => (unpinLevel(), zoomAt(LEVEL_ZOOM[l]))} data-testid={`live-level-${l}`} title={SAYS[l]}>
          {l}
        </button>
      ))}
    </span>
  );
}
