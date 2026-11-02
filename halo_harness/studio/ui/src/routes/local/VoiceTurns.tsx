// Local -> Voice, the last turns (3.3.9.0 R3; voice/turns.jsonl through GET local/voice): each latency card's line,
// newest first (the terminal loop's, Talk's and the voice door's, marked by where it came from), `halo voice stats`
// over the newest 50 (the median and worst per stage against the budget, the slow stage named), the steward's
// voice-slow when a stage ran over its share three turns running, and this machine's microphones and speakers (the
// terminal loop's devices; Talk uses the browser's).
import { useVoice } from "./voicestore";

export function VoiceTurns() {
  const turns = useVoice((v) => v.view?.turns);
  const stats = useVoice((v) => v.view?.stats);
  const slow = useVoice((v) => v.view?.findings);
  const devices = useVoice((v) => v.view?.devices);
  return (
    <>
      <section className="pool-block" aria-label="The last turns" data-testid="voice-turns">
        <div className="rail-label mono">THE LAST TURNS · THEIR LATENCY CARDS</div>
        {turns && !turns.length && <p className="mono muted">no voice turns yet: Talk, `halo voice` or the voice door leave one each</p>}
        {turns && turns.length > 0 && (
          <ul className="pool-card-lines" data-count={turns.length}>
            {turns.map((t) => (
              <li key={`${t.at}|${t.line}`} className="mono" data-testid="voice-turn" data-via={t.via || "loop"}>
                {t.line}{t.via ? ` (${t.via === "host" ? "the voice door" : t.via})` : ""}
              </li>
            ))}
          </ul>
        )}
        {stats && (
          <ul className="pool-card-lines" data-testid="voice-stats">
            {stats.lines.map((l) => <li key={l} className="mono muted">{l}</li>)}
          </ul>
        )}
        {(slow || []).filter((f) => f.key.startsWith("voice|")).map((f) => (
          <p key={f.id} className="mono vc-finding" data-severity={f.severity} data-testid="voice-slow">{f.rule}: {f.finding}</p>
        ))}
      </section>
      <section className="pool-block" aria-label="Devices" data-testid="voice-devices">
        <div className="rail-label mono">THIS MACHINE'S DEVICES · THE TERMINAL LOOP'S</div>
        {devices?.error && <p className="mono muted">{devices.error}</p>}
        {devices && (
          <ul className="pool-card-lines">
            {devices.inputs.map((d) => <li key={`i${d.index}`} className="mono" data-testid="voice-device" data-kind="input">microphone {d.index}: {d.name}{d.default ? " (default)" : ""}</li>)}
            {devices.outputs.map((d) => <li key={`o${d.index}`} className="mono" data-testid="voice-device" data-kind="output">speaker {d.index}: {d.name}{d.default ? " (default)" : ""}</li>)}
            {!devices.inputs.length && !devices.outputs.length && !devices.error && <li className="mono muted">none listed (halo voice devices)</li>}
          </ul>
        )}
      </section>
    </>
  );
}
