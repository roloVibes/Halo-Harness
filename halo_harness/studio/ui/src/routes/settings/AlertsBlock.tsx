// Settings -> Studio -> Alerts (3.4.1.0 R4; lib/alerts.ts, docs/STUDIO-live.md "The alert"): the channel one alert goes
// by when something starts waiting on you -- None (the default: nothing is sent) or each channel of lib/alerts.ts
// CHANNELS (today: this browser's notification). Choosing the browser asks THIS browser for permission then, on that
// click (the only place Studio asks; never on load), and saves `studio.alerts`; the line under the choices says what
// this browser will do. The `studio.alerts` row below stays generic (a terminal's `halo config set` moves the same key).
import { useState } from "react";
import { ALERT_KEY, CHANNELS, chosenOf, type ChannelState } from "../../lib/alerts";
import { setValue, useSettings } from "./store";

const STATE_WORDS: Record<ChannelState, string> = {
  ready: "this browser allows it: a new ask shows one notification here, a click on it opens the ask",
  ask: "this browser has not been asked yet: press This browser's notification above and it asks, once",
  blocked: "this browser blocked notifications for this page: allow them in its site settings for this address",
  none: "this browser gives no notifications on this page (a page off 127.0.0.1 or localhost has none)",
};

type Choice = { id: string; label: string; what: string };
const NONE: Choice = { id: "none", label: "None", what: "nothing is sent (the default); writes studio.alerts in config.json" };

export function AlertsBlock() {
  const pick = useSettings((s) => chosenOf(s.values[ALERT_KEY]));
  const busy = useSettings((s) => s.busy === ALERT_KEY);
  const [, redraw] = useState(0);
  const choose = async (id: string) => {
    const ch = CHANNELS[id];
    if (ch?.ask && ch.state() === "ask") await ch.ask(); // the owner's click: the one place a channel asks
    await setValue(ALERT_KEY, id);
    redraw((n) => n + 1);
  };
  const choices: Choice[] = [NONE, ...Object.values(CHANNELS).map((c) => ({ id: c.id, label: c.label, what: c.what }))];
  const ch = CHANNELS[pick];
  const state = ch ? ch.state() : null;
  return (
    <section className="st-ollama al-block" data-testid="settings-alerts" data-choice={pick} aria-label="Alerts">
      <div className="st-ollama-row">
        <b>Alerts</b>
        <span className="muted">when something starts waiting on you: one alert, naming what waits and on which session</span>
      </div>
      <div className="al-choices" role="radiogroup" aria-label="How an alert reaches you">
        {choices.map((c) => (
          <button key={c.id} type="button" role="radio" aria-checked={pick === c.id} className="al-choice" data-testid="settings-alerts-choice"
                  data-id={c.id} disabled={busy} onClick={() => void choose(c.id)} title={c.what}>
            <span className="al-dot" aria-hidden="true" />
            <span className="al-label">{c.label}</span>
            <span className="al-what muted">{c.what}</span>
          </button>
        ))}
      </div>
      {state && (
        <p className="al-state mono" data-testid="settings-alerts-state" data-state={state}>
          {STATE_WORDS[state]}
        </p>
      )}
    </section>
  );
}
