// The alert (3.4.1.0 R4; `studio.alerts`, Settings -> Studio -> Alerts; docs/STUDIO-live.md "The alert"): when
// something STARTS waiting on you -- a new row of the attention queue (a permission, a question, a plan, a gate, a cap)
// -- ONE alert by the channel you picked, naming what waits and on which session. Never one per feed event (a card is
// one row however many frames say it), never for what already waited when the page opened, and several rows that land
// together are one alert ("and 2 more"). CHANNELS is a table: "none" (the default) sends nothing; `browser` is this
// browser's notification, asked for once on your click in the Alerts block (routes/settings/AlertsBlock.tsx calls
// `ask`), never here and never on load. A second channel is one more entry of CHANNELS. A click on a notification
// opens the ask: the page that starts the watch (the shell, the glance) says how.
import { panels, type AttnRow } from "../routes/fleet/pstore";
import { settings, startSettings, type Value } from "../routes/settings/store";

export const ALERT_KEY = "studio.alerts";
/** What this browser lets a channel do: send now, ask first (on a click), refused by the browser, or not here at all. */
export type ChannelState = "ready" | "ask" | "blocked" | "none";
export type Alert = { title: string; body: string; tag: string; row: AttnRow };
export type Channel = {
  id: string;
  label: string;
  /** What choosing it does, costs and writes, in one line. */
  what: string;
  state: () => ChannelState;
  /** Ask for what the channel needs (a click handler calls it; nothing else does). */
  ask?: () => Promise<ChannelState>;
  send: (a: Alert, open: (row: AttnRow) => void) => boolean;
};

/** The browser's Notification, read at each use (absent off a secure page, or in a browser without it). */
function notes(): typeof Notification | null {
  try {
    if (typeof window === "undefined" || !("Notification" in window)) return null;
    return window.isSecureContext === false ? null : window.Notification;
  } catch {
    return null;
  }
}

const browser: Channel = {
  id: "browser",
  label: "This browser's notification",
  what: "asks this browser once, now; one notification per new ask on each Studio page or glance it allows; writes studio.alerts in config.json; costs nothing",
  state: () => {
    const N = notes();
    if (!N) return "none";
    return N.permission === "granted" ? "ready" : N.permission === "denied" ? "blocked" : "ask";
  },
  ask: async () => {
    const N = notes();
    if (N && N.permission === "default") {
      try {
        await N.requestPermission();
      } catch {
        /* an old browser's callback form, or a refusal: the state says what it is */
      }
    }
    return browser.state();
  },
  send: (a, open) => {
    const N = notes();
    if (!N || N.permission !== "granted") return false;
    try {
      const n = new N(a.title, { body: a.body, tag: a.tag });
      n.onclick = () => {
        try {
          window.focus();
        } catch {
          /* a browser that keeps focus to itself */
        }
        open(a.row);
        n.close();
      };
      return true;
    } catch {
      return false;
    }
  },
};

export const CHANNELS: Record<string, Channel> = { browser };

/** The channel `studio.alerts` names ("none" when unset, unknown or a channel this build does not have). */
export function chosenOf(v: Value | undefined): string {
  const x = v ? (v.set ? v.value : v.default) : "none";
  return typeof x === "string" && CHANNELS[x] ? x : "none";
}

/** One alert for the rows that just started waiting (the first named, the rest counted). */
export function alertOf(rows: AttnRow[]): Alert | null {
  const r = rows[0];
  if (!r) return null;
  const where = r.session ? `${r.session} on ${r.harness_name}` : r.harness_name;
  const more = rows.length > 1 ? ` (and ${rows.length - 1} more)` : "";
  return { title: `Waiting on you: ${r.what}`, body: `${where}${r.agent ? " · " + r.agent : ""}${more}`, tag: "halo-ask-" + r.id, row: r };
}

let seen: Set<string> | null = null; // null until the first read: what already waited when the page opened is not news
let last: AttnRow[] | null = null;
let opener: (row: AttnRow) => void = () => undefined;
let started = false;

function check(): void {
  const s = panels.get();
  if (!s.attnLoaded || s.attnError || s.attention === last) return;
  last = s.attention;
  if (seen === null) {
    seen = new Set(s.attention.map((r) => r.id));
    return;
  }
  const fresh = s.attention.filter((r) => !seen!.has(r.id));
  for (const r of fresh) seen.add(r.id);
  if (!fresh.length) return;
  const ch = CHANNELS[chosenOf(settings.get().values[ALERT_KEY])];
  const a = alertOf(fresh);
  if (ch && a) ch.send(a, (row) => opener(row));
}

/** Watch the attention queue for this page (the shell and the glance each start it once); `open` shows a clicked ask. */
export function startAlerts(open: (row: AttnRow) => void): void {
  opener = open;
  if (started) return;
  started = true;
  startSettings();
  panels.subscribe(check);
  check();
}
