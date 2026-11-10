// fleet-capabilities (3.0.6.0 R6): what every harness can do, one spec card
// each: hardware, models, craft apps, media, MCP servers (each opens to its
// tools), skills, command-line tools, tags, the packs' fleet capabilities
// (3.2.0.0 R4, PackCaps.tsx: each available or not and why), the catalog's age and Refresh;
// the "Who can..." box on top ranks the fleet for what you need (Who.tsx);
// 3.1.8.0 R4: under it in the full face, the recall box (Recall.tsx).
// Catalogs are computed in code on each harness and cached there; a member
// sends a new one when it changes (the hub asks once per hash), so a card
// is only as old as its age says. Compact face (the default, so the Agent
// panel under it keeps its height): the Who box and its best three, else
// each harness's chips; Expand for the spec cards.
import { type ReactNode } from "react";
import { Button, Icon } from "../../lib/ui";
import { loadCaps, useCaps, type Catalog, type CapsRow } from "./caps";
import { age } from "./pstore";
import { PackCapsLine } from "./PackCaps";

const tools = (c: Catalog | null) => (c?.mcp || []).reduce((n, s) => n + (s.tools?.length || 0), 0);

function Line({ k, children }: { k: string; children: ReactNode }) {
  return <><dt>{k}</dt><dd>{children}</dd></>;
}

function list(items: string[], none = "none", n = 12): string {
  if (!items.length) return none;
  return items.slice(0, n).join(", ") + (items.length > n ? ` +${items.length - n} more` : "");
}

function Servers({ c }: { c: Catalog }) {
  if (!c.mcp.length) return <span className="muted">none</span>;
  return (
    <div className="fcap-mcp">
      {c.mcp.map((s) => (
        <details key={s.name} className="fcap-server" data-testid="fleet-caps-server" data-name={s.name}>
          <summary>
            <span className="mono">{s.name}</span>
            <span className="og-chip mono" data-none={s.tools ? undefined : true}>{s.tools ? `${s.tools.length} tools` : "tools ?"}</span>
            {s.note && <span className="muted fcap-note">{s.note}</span>}
          </summary>
          {s.tools && s.tools.length > 0 && (
            <ul className="fcap-tools">
              {s.tools.map((t) => <li key={t.name} data-testid="fleet-caps-tool"><b className="mono">{t.name}</b> <span className="muted">{t.desc}</span></li>)}
            </ul>
          )}
        </details>
      ))}
    </div>
  );
}

export function CapsCard({ r, now }: { r: CapsRow; now: number }) {
  const focus = useCaps((s) => s.focus === r.harness);
  const busy = useCaps((s) => s.busy === r.harness || (r.local && s.busy === "local"));
  const c = r.catalog;
  const hw = c?.hardware || {};
  const gpu = (hw.gpu || []).map((g) => `${g.name}${g.vram_gb ? ` ${g.vram_gb} GB` : ""}`);
  return (
    <li className="fcap-card" data-testid="fleet-caps-card" data-id={r.harness} data-focus={focus || undefined}>
      <div className="fcap-head">
        <b>{r.name}</b>
        <span className="og-chip mono">{r.local ? "this harness" : r.online ? "online" : "offline"}</span>
        {r.chips.map((x) => <span key={x} className="og-chip mono fcap-chip" data-testid="fleet-caps-chip">{x}</span>)}
        <span className="spacer" />
        <span className="mono muted" title={`catalog hash ${r.hash || "-"}`} data-testid="fleet-caps-age">{r.at ? `${age(r.at, now)} old` : "no catalog"}</span>
        <Button size="sm" variant="ghost" icon={<Icon name="reset" />} disabled={busy} data-testid="fleet-caps-refresh"
                title={r.local ? "gather this harness's catalog again now" : "ask it for a fresh catalog now"} onClick={() => void loadCaps(true, r.local ? "local" : r.harness)}>
          {busy ? "Asking..." : "Refresh"}
        </Button>
      </div>
      {!c ? <p className="muted fcap-note">{r.note || r.summary || "no catalog yet"}</p> : (
        <dl className="fcap-facts">
          <Line k="hardware"><span className="mono">{[hw.cpu, hw.cores ? `${hw.cores} cores` : "", hw.ram_gb ? `${hw.ram_gb} GB RAM` : "", ...(gpu.length ? gpu : ["no GPU found"]), hw.disk_free_gb != null ? `${hw.disk_free_gb} GB free` : ""].filter(Boolean).join(" · ")}</span></Line>
          <Line k="models">{list(c.models.map((m) => m.id + (m.best_for.length ? ` (${m.best_for.join(", ")})` : m.local ? " (local)" : "")), "none", 6)}</Line>
          <Line k="craft apps">{list(c.craft_apps)}</Line>
          {c.media?.comfyui && <Line k="media">ComfyUI · {list(c.media.models.map((m) => `${m.name} (${m.kind})`), "no models scanned", 4)}</Line>}
          <Line k={`mcp (${tools(c)})`}><Servers c={c} /></Line>
          <Line k="skills">{list(c.skills, "none", 10)}</Line>
          <Line k="clis"><span className="mono">{list(Object.entries(c.clis || {}).filter(([, v]) => v).map(([k, v]) => (v === "installed" ? k : `${k} ${v}`)), "none", 14)}</span></Line>
          {(c.packs || []).some((p) => p.capabilities.length > 0) && <Line k="packs"><PackCapsLine c={c} /></Line>}
          <Line k="tags">{list(c.tags, "none (fleet.tags)")}</Line>
        </dl>
      )}
    </li>
  );
}
