// 3.4.1.0 R3 (the living canvas part 2, item 7): Session's bar says the session's permission mode as one small word --
// auto, default, acceptEdits, plan, bypassPermissions, dontAsk -- with the mode's one-line meaning on hover (the words
// agent/mode_notice.py gives the model each turn), so "what mode is this session in" is on the page. Read from the
// session's row: the registry's `mode`, kept current by the session's own status events (remote/runtime.py), so Shift+Tab
// in the terminal or `/plan on` moves it. Nothing shows before the session has said.
import { useFleet } from "../fleet/store";
import { chosenSession } from "./store";

export const MODE_MEANING: Record<string, string> = {
  auto: "every call runs except your own deny and ask rules",
  default: "edits and commands ask you first",
  acceptEdits: "edits in the working directory run without asking; commands ask first",
  plan: "read-only: the agent writes a plan and asks you to approve it",
  bypassPermissions: "every call runs",
  dontAsk: "only the calls your rules allow run; the rest are refused",
};

/** The mode a session reports, as its word ("manual" is default's other name). */
export const modeWord = (mode: string | null | undefined): string => (mode === "manual" ? "default" : String(mode || ""));

export function ModeWord() {
  const ss = useFleet(chosenSession);
  const word = modeWord(ss?.mode);
  if (!word) return null;
  return (
    <span className="og-chip mono slv-mode" data-testid="session-mode" data-mode={word}
          title={`Permission mode: ${word} -- ${MODE_MEANING[word] || "a mode this Studio has no words for"}. Shift+Tab in the terminal or /plan changes it.`}>
      {word}
    </span>
  );
}
