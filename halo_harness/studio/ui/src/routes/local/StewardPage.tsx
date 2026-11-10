// Local -> Steward (3.3.7.0 R5; built from the 3.3.5.0 R1 frame): the steward job's status line and last note (the
// steward block, GET ollama/steward), the off-hours refresh (R4), the steward's model and its
// candidates, and the chat box over the host's findings (StewardChat.tsx); 3.3.8.0 R2: the findings of every host and
// local server (StewardFindings.tsx).
import { useEffect } from "react";
import { NoteLines, StewardRunAndChanges } from "./StewardBits";
import { loadSteward, startOllamaFeed, useOllama } from "./ostore";
import { StewardChat } from "./StewardChat";
import { StewardFindings } from "./StewardFindings";
import { StewardModel } from "./StewardModel";
import { StewardRefresh } from "./StewardRefresh";

function StewardNow() {
  const lines = useOllama((s) => s.steward?.status_lines || null);
  const note = useOllama((s) => s.steward?.last_note || null);
  useEffect(() => {
    startOllamaFeed();
    void loadSteward();
  }, []);
  return (
    <section className="lc-block" aria-label="The steward now" data-testid="local-steward-now">
      <div className="rail-label mono">THE STEWARD NOW</div>
      <div className="mono muted lc-status" data-testid="local-steward-status">
        {(lines || ["reading the steward..."]).map((l) => (
          <div key={l}>{l.trim()}</div>
        ))}
      </div>
      <NoteLines note={note} testid="local-steward-note" />
      <StewardRunAndChanges />
    </section>
  );
}

export function StewardPage() {
  return (
    <div className="lc-steward" data-testid="local-steward-page">
      <StewardNow />
      <StewardFindings />
      <StewardChat />
      <StewardModel />
      <StewardRefresh />
    </div>
  );
}
