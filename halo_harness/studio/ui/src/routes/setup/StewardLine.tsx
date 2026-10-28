// Setup -> Providers' Ollama card, its steward line (3.3.4.0 R5): one muted line, "steward: <the first line
// of its last note>" (or "no note yet"), and a link that opens Fleet's Ollama panel. Read once from
// `GET ollama/steward` when the card shows (routes/fleet/ostore.ts).
import { useEffect } from "react";
import { openOllama } from "../fleet/Ollama";
import { loadSteward, useOllama } from "../fleet/ostore";

export function StewardLine() {
  useEffect(() => {
    void loadSteward();
  }, []);
  const note = useOllama((s) => s.steward?.last_note);
  const read = useOllama((s) => !!s.steward);
  const first = note ? (note.lines?.length ? note.lines[0] : note.say) : "";
  return (
    <p className="muted su-steward mono" data-testid="setup-steward-line">
      <span data-testid="setup-steward-text">{read ? (first ? `steward: ${first}` : "steward: no note yet") : "steward: reading..."}</span>{" "}
      <button type="button" className="link-btn" onClick={openOllama} data-testid="setup-steward-open">Open the Ollama panel</button>
    </p>
  );
}
