// The Live column's foot (3.1.7.0 R1, "the steer is always at hand"): the
// Steer box, there at all times. It talks to the pinned agent, or, with none
// pinned, to the chosen session's main agent; its header says who ("STEER
// main", "STEER researcher") in that agent's colour, and Pause and Stop sit
// beside it for that same agent (Stop asks first: the Fleet confirm dialog).
// When that agent has finished the box is disabled and says so in one line.
// A steer sent here echoes in the column as a YOU line at once
// (shared/liveTree.ts) and lands in the agent's next step.
import { Button, Icon } from "../../lib/ui";
import { askStop, togglePause } from "../fleet/actions";
import { Steer } from "../fleet/Steer";
import { hueOf } from "../shared/hues";
import { useSteerTarget } from "./steer";

const FINISHED = ["done", "failed", "stopped"];

export function LiveSteer() {
  const t = useSteerTarget();
  if (!t.key)
    return <div className="slv-hint mono muted" data-testid="session-live-hint">No session here yet: start one in a terminal (halo) and steer it from here.</div>;
  const a = t.ref?.a;
  const name = t.main ? "main" : a?.name || a?.role || a?.agent_id || t.key.split("|")[2] || "?";
  const noControl = t.ref?.h.allow_control === "none";
  const done = !a || FINISHED.includes(String(a.state));
  const why = !a
    ? `${name} is not in this session any more: pin a live agent (its tag, its lane or the agent pick)`
    : noControl
      ? `${t.ref?.h.name || "that harness"} takes no commands from here (allow_control none)`
      : done
        ? `${name} has finished (${a.state}): nothing to steer; pin a live agent (its tag, its lane or the agent pick)`
        : undefined;
  const paused = a?.state === "paused";
  const head = (
    <span className="slv-steer-to" title={a ? `${a.name || a.agent_id}: ${a.state}${t.main ? " (the session's main agent)" : ""}` : undefined}>
      <span className="rail-label mono">STEER</span>
      <span className="mono slv-steer-name" data-testid="session-live-steer-to">{name}</span>
    </span>
  );
  const extra = (
    <>
      <Button size="sm" icon={<Icon name={paused ? "play" : "pause"} />} disabled={!!why} onClick={() => void togglePause(t.key)} data-testid="session-live-pause"
              title={why || (paused ? `Resume ${name}` : `Pause ${name} at its next step`)}>
        {paused ? "Resume" : "Pause"}
      </Button>
      <Button size="sm" variant="danger" icon={<Icon name="stop" />} disabled={!!why} onClick={() => askStop(t.key)} data-testid="session-live-stop"
              title={why || `Stop ${name} at its next step (asks first)`}>
        Stop
      </Button>
    </>
  );
  return (
    <div className="slv-steer holo-frame" data-testid="session-live-steer" data-key={t.key} data-hc={hueOf(t.key)} data-main={t.main || undefined} data-disabled={!!why || undefined}>
      <Steer key={t.key} k={t.key} where="live" disabled={!!why} why={why} head={head} extra={extra} />
    </div>
  );
}
