// Fleet capabilities from packs (3.2.0.0 R4), in three places:
// - the Capabilities card's "packs" line: each capability a harness's packs
//   bring, available there or not and why (the catalog's `packs` section,
//   halo_harness/packs/fleet_registry.py);
// - the Mission plan's needs cell: a need a pack capability meets names its
//   pack and the harness that has it (the part's `pack_needs`);
// - the pack's inspector lines (contributes.fleet.inspector) under the
//   selected part and in the Agent panel of a part's agent: each file is read
//   through the pack's file route (api/pack/<id>/file/<source>) when the pack
//   runs on this harness; a pack only on another harness shows the text its
//   catalog carries (3.2.1.0 R3: the file's first 8 KB, paths cut, read there
//   by packs/fleet_share.py), else its labels and where it runs.
import { useEffect, useState } from "react";
import { Markdown } from "../../lib/markdown";
import { fetchText } from "../packs/nav";
import { startCaps, useCaps, type Catalog, type InspectorEntry } from "./caps";
import { useMissions, type PlanPart } from "./mstore";

export function PackCapsLine({ c }: { c: Catalog }) {
  const all = (c.packs || []).flatMap((p) => p.capabilities.map((x) => ({ pack: p.id, x })));
  if (!all.length) return null;
  return (
    <ul className="fcap-packs" data-testid="fleet-caps-packs">
      {all.map(({ pack, x }) => (
        <li key={`${pack}/${x.name}`} data-testid="fleet-caps-pack" data-name={x.name} data-available={x.available ? "yes" : "no"} title={x.description}>
          <span className="og-chip mono" data-none={x.available ? undefined : true}>{x.name}</span>
          <span className="mono muted"> pack {pack}{x.capacity?.parallel ? ` · ${x.capacity.parallel} at once` : ""} · </span>
          <span className="fcap-why" data-testid="fleet-caps-pack-why">{x.available ? "available" : "not available"}: {x.why}</span>
        </li>
      ))}
    </ul>
  );
}

/** A part's needs: a need a pack capability meets is a chip naming the pack and the harness that has it. */
export function PackNeeds({ p }: { p: PlanPart }) {
  const packOf = new Map((p.pack_needs || []).map((x) => [x.need, x.pack]));
  if (!p.needs.length) return <>-</>;
  return (
    <>
      {p.needs.map((n, i) => {
        const pack = packOf.get(n);
        if (!pack) return <span key={n}>{i ? ", " : ""}{n}</span>;
        return (
          <span key={n} className="og-chip mono fmi-packneed" data-testid="fleet-mission-pack-need" data-need={n} data-pack={pack}
                title={`a capability of pack ${pack}; ${p.harness_name || "no harness"} runs that pack with its grants`}>
            {n} · pack {pack} on {p.harness_name || "?"}
          </span>
        );
      })}
    </>
  );
}

function jsonLines(text: string): string {
  try {
    const data = JSON.parse(text);
    if (Array.isArray(data)) return data.map((r) => (r && typeof r === "object" ? Object.values(r).join(" · ") : String(r))).join("\n");
    if (data && typeof data === "object") return Object.entries(data).map(([k, v]) => `${k}: ${typeof v === "object" ? JSON.stringify(v) : String(v)}`).join("\n");
    return String(data);
  } catch {
    return text;
  }
}

function Body({ source, text }: { source: string; text: string }) {
  return source.toLowerCase().endsWith(".json") ? <pre className="fpk-text mono">{jsonLines(text)}</pre> : <div className="fpk-md"><Markdown text={text} /></div>;
}

function InspectorLine({ pack, x, local, on }: { pack: string; x: InspectorEntry; local: boolean; on: string }) {
  const { label, source } = x;
  const [st, setSt] = useState({ text: "", error: "", loading: local });
  useEffect(() => {
    if (!local) return;
    let live = true;
    const path = `api/pack/${encodeURIComponent(pack)}/file/${source.split("/").map(encodeURIComponent).join("/")}`;
    fetchText(path).then(
      (text) => live && setSt({ text, error: "", loading: false }),
      (e) => live && setSt({ text: "", error: e instanceof Error ? e.message : String(e), loading: false }),
    );
    return () => {
      live = false;
    };
  }, [pack, source, local]);
  return (
    <div className="fpk-line" data-testid="fleet-pack-inspector-line" data-pack={pack} data-label={label} data-local={local ? "yes" : "no"}>
      <div className="fpk-line-head"><b>{label}</b> <span className="mono muted">pack {pack} · {source}{local ? "" : ` · on ${on || "another harness"}`}</span></div>
      {!local ? (typeof x.text === "string"
          ? <><Body source={source} text={x.text} />{x.cut && <p className="muted mono" data-testid="fleet-pack-inspector-cut">the first 8 KB of {source}</p>}</>
          : <p className="muted">pack {pack} runs on {on || "another harness"}; its Studio reads this file.</p>)
        : st.loading ? <div className="og-wait mono muted">reading {source}...</div>
        : st.error ? <p className="og-problems">{st.error}</p>
        : <Body source={source} text={st.text} />}
    </div>
  );
}

/** The inspector lines of the packs `ids`, as this harness's catalog (else the part's harness's) lists them. */
export function PackInspector({ ids, harness, on }: { ids: string[]; harness?: string | null; on: string }) {
  useEffect(() => startCaps(), []);
  const rows = useCaps((s) => s.rows);
  const packs = [...new Set(ids)];
  if (!packs.length) return null;
  const local = rows?.find((r) => r.local)?.catalog?.packs || [];
  const there = rows?.find((r) => r.harness === harness)?.catalog?.packs || [];
  return (
    <section className="fpk-inspector" data-testid="fleet-pack-inspector">
      <div className="rail-label mono">PACK INSPECTOR</div>
      {packs.map((id) => {
        const mine = local.find((p) => p.id === id);
        const entry = mine || there.find((p) => p.id === id);
        if (!entry) return <p key={id} className="muted">pack {id}: no catalog Studio has lists it yet</p>;
        if (!entry.inspector.length) return <p key={id} className="muted">pack {id} declares no inspector lines</p>;
        return entry.inspector.map((x) => <InspectorLine key={`${id}/${x.source}`} pack={id} x={x} local={!!mine} on={on} />);
      })}
    </section>
  );
}

/** The selected part's pack inspector (the Mission plan). */
export function PartPackInspector({ p }: { p: PlanPart | undefined }) {
  if (!p?.pack_needs?.length) return null;
  return <PackInspector ids={p.pack_needs.map((x) => x.pack)} harness={p.harness} on={p.harness_name || ""} />;
}

/** In the Agent panel: the pack inspector of the mission part this agent's session runs, when that mission is open. */
export function AgentPackInspector({ mission, part }: { mission?: string | null; part?: string | number | null }) {
  const view = useMissions((s) => s.view);
  if (!mission || part === undefined || part === null || view?.mission.id !== mission) return null;
  const p = view.plan?.parts.find((x) => x.id === String(part));
  return <PartPackInspector p={p} />;
}

/** A mission's metadata line (the pack whose lineup started it). */
export function MissionMeta() {
  const meta = useMissions((s) => s.view?.mission.metadata);
  if (!meta || !Object.keys(meta).length) return null;
  const { pack, lineup, ...rest } = meta as Record<string, unknown>;
  const text = Object.entries(rest).map(([k, v]) => `${k}=${Array.isArray(v) ? v.join(",") : String(v)}`).join(" · ");
  return (
    <div className="fmi-head-sub mono muted" data-testid="fleet-mission-metadata" title={`started by the lineup ${String(lineup || "")}`}>
      pack {String(pack || "?")}{text ? ` · ${text}` : ""}
    </div>
  );
}
