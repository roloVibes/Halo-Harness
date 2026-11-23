// 3.6.0.15 F3: Pause says what a press does. One fact, one rule for every Pause / Resume door (the sheet's button, the
// feed's box head, Agents' detail and its palette command, Session's steer row, togglePause): a pause is SET while the
// agent holds ("paused") or while its row says a pause was pressed on it and not yet taken back (`pause_set`, from the
// controls: agent/agent_inbox.py), also before it holds (a helper that waits on an ask holds at the call after it).
// A set pause is not a state: every state word and badge stays on `state`.
export type PauseFacts = { state?: string | null; pause_set?: boolean | null } | null | undefined;

export const pauseSet = (a: PauseFacts): boolean => !!a && (a.state === "paused" || !!a.pause_set);

export const pauseWord = (a: PauseFacts): "Resume" | "Pause" => (pauseSet(a) ? "Resume" : "Pause");
