// A session box's and a machine box's hover cards (3.3.16.1). A session: its whole title, where it works (project,
// branch, clean / dirty, ahead / behind, worktree), its kind when it is not the terminal's, its model, cost, agents live
// of all, what waits on you and since when it runs. A click selects its main agent: the agent inspector. A machine: its
// host, this halo or its presence, its Halo version (a mismatch said in words), its sessions and live agents, what it
// spent today (and its cap), every capability it has (the box shows three), its GPU and memory when its spec card is
// loaded. A click puts it in the inspector: its summary.
import { short } from "../../orchestra/format";
import { useCaps } from "../../fleet/caps";
import { presence } from "../../fleet/People";
import { usePanels } from "../../fleet/pstore";
import { isLive, useFleet, useNow } from "../../fleet/store";
import type { SessionRow } from "../../fleet/types";
import { HoverBody, type HoverRow } from "../../../lib/hover/HoverBody";
import { ago, joined, plural, spent } from "./words";

/** "2 asks · the oldest: git push origin feature/basket", "" when nothing waits. */
function waits(s: SessionRow): string {
  const asks = Object.values(s.pending || {}).flatMap((v) => v || []);
  const waiting = (s.agents || []).filter((a) => a.state === "waiting").length;
  const n = Math.max(asks.length, waiting);
  if (!n) return "";
  return joined([plural(n, "ask"), asks[0] && `the oldest: ${short(asks[0], 48)}`]);
}

export function SessionHover({ hid, sid, title }: { hid: string; sid: string; title: string }) {
  const s = useFleet((st) => st.harnesses.find((h) => h.id === hid)?.sessions.find((x) => x.session_id === sid));
  const room = usePanels((st) => st.conflicts?.rooms.flatMap((r) => r.cards).find((x) => x.harness === hid && x.session_id === sid));
  if (!s) return null;
  const p = s.project || {};
  const folder = String(p.repo || p.root || s.cwd || "").replace(/[\\/]+$/, "").split(/[\\/]/).pop() || "";
  const dirty = room?.dirty ?? p.dirty;
  const where = joined([folder, p.branch, p.branch && (dirty ? "dirty" : "clean"), !!room?.ahead && `ahead ${room.ahead}`, !!room?.behind && `behind ${room.behind}`,
                        !!room?.worktree && `worktree ${String(room.worktree).replace(/[\\/]+$/, "").split(/[\\/]/).pop()}`]);
  const agents = s.agents || [];
  const kind = s.kind && s.kind !== "tui" ? (s.kind === "headless" ? "no terminal (started from Studio)" : s.kind) : "";
  const cost = spent(s.cost_usd);
  const rows: HoverRow[] = [
    ["Where", where],
    ["Kind", kind],
    ["Model", joined([s.model, s.effort])],
    ["Cost", cost && (s.cost_complete === false ? `${cost}+ (a model gave no price)` : cost)],
    ["Agents", agents.length ? `${agents.filter(isLive).length} live of ${agents.length}` : ""],
    ["Waits on you", waits(s)],
    ["Started", ago(s.started)],
  ];
  return <HoverBody title={title} is={s.cwd ? `A session in ${s.cwd}` : "A session of this machine"} rows={rows} foot="Click: its main agent in the inspector" />;
}

export function MachineHover({ hid }: { hid: string }) {
  const h = useFleet((s) => s.harnesses.find((x) => x.id === hid));
  const caps = useCaps((s) => s.rows?.find((r) => r.harness === hid));
  const cap = usePanels((s) => s.costs?.caps?.per_harness_usd_per_day);
  const now = useNow(false);
  if (!h) return null;
  const sessions = h.sessions || [];
  const live = sessions.reduce((n, s) => n + (s.agents || []).filter(isLive).length, 0);
  const hw = caps?.catalog?.hardware;
  const gpu = (hw?.gpu || []).map((g) => `${g.name}${g.vram_gb ? ` ${g.vram_gb} GB` : ""}`).join(", ");
  const today = spent(h.cost_today);
  const rows: HoverRow[] = [
    ["Host", joined([h.host, h.os])],
    h.local ? ["This halo", "yes: this Studio runs here"] : ["Presence", { live: "live: an agent works", idle: "idle", away: "away: not heard from lately" }[presence(h, now)]],
    ["Halo version", h.version ? (h.version_mismatch ? `${h.version}: another version than this halo's (halo update on the older one)` : h.version) : ""],
    ["Sessions", `${plural(sessions.length, "session")} · ${live} live agent${live === 1 ? "" : "s"}`],
    ["Spent today", today ? joined([today, cap != null && `cap $${cap} a day`]) : cap != null ? `nothing yet · cap $${cap} a day` : ""],
    ["What it has", (caps?.chips || []).join(", ")],
    ["GPU", gpu],
    ["Memory", hw?.ram_gb ? `${hw.ram_gb} GB RAM${hw.cores ? ` · ${hw.cores} cores` : ""}` : ""],
  ];
  return <HoverBody title={String(h.name || hid.slice(0, 8))} is={h.local ? "This machine: the halo this Studio runs on." : "A machine of your fleet."}
                    rows={rows} foot="Click: its summary in the inspector" />;
}
