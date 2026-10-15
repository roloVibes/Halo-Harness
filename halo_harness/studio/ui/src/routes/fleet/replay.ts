// Canvas replay (D12), the shell's half: a finished session played back on
// the Roles canvas. The framed page asks `{type: "fleet-replay-open",
// session, harness}` (its Live tab's history rows have a "replay" button),
// the Fleet agent panel's history and the palette call openReplay; the shell
// reads `GET fleet/replay` and posts `{type: "fleet-replay", events, meta}`
// into the Roles frame, where static/legacy/replay.js draws the scrub bar
// and lights the cards in the order they worked. The frame never calls the
// fleet routes itself.
import { api, ApiError } from "../../lib/api";
import { goSection, toast } from "../../lib/store";

type ReplayView = { harness: string; session_id: string; title: string; started: number; ended: number; cost_usd: number; agents: unknown[]; states: unknown[]; costs: unknown[] };

const FRAME = '.section-view[data-section="roles"] iframe.legacy-frame';

/** The Roles frame once its page is up (replay.js loaded), or null after `ms`. */
async function rolesFrame(ms = 20000): Promise<Window | null> {
  const end = Date.now() + ms;
  while (Date.now() < end) {
    const w = document.querySelector<HTMLIFrameElement>(FRAME)?.contentWindow as (Window & { haloReplay?: unknown; app?: { canvas?: { nodes?: unknown[] } } }) | null;
    try {
      if (w && w.haloReplay && w.app?.canvas?.nodes?.length) return w;
    } catch {
      /* the frame is between pages */
    }
    await new Promise((r) => window.setTimeout(r, 150));
  }
  return null;
}

export async function openReplay(session: string, harness = "local", into?: Window | null): Promise<boolean> {
  let view: ReplayView;
  try {
    view = await api.get<ReplayView>("fleet/replay", { session, harness });
  } catch (e) {
    toast(`No replay: ${e instanceof ApiError ? e.message : String(e)}`, "error", 5000);
    return false;
  }
  if (!view.states?.length) {
    toast("That session left no agent history to replay", "info", 4000);
    return false;
  }
  if (!into) goSection("roles");
  const w = into || (await rolesFrame());
  if (!w) {
    toast("The Roles canvas did not open: open Roles, then try again", "error", 5000);
    return false;
  }
  const { states, ...meta } = view;
  w.postMessage({ type: "fleet-replay", events: states, meta }, location.origin);
  return true;
}
