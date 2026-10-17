// The Team board's parts (3.0.8.0 R2): a member's column (its labelled box:
// name, lineup and role, the harness chip, the live chips of the stages it
// works in right now), a stage's box (state colour, kind, members, lead, the
// gate diamond, the line that matters: waiting, error, summary or trigger),
// a block's node (a document, folder or git glyph, the claims mode, the claim
// badge: holders, amber while someone writes, and its last change) and an
// edge. A click selects; the Inspector follows the selection.
import { short } from "../orchestra/format";
import type { Column, Edge, StageBox, BlockBox } from "./layout";
import { HEAD } from "./layout";
import { claimState, stageMotion, usd } from "./store";
import type { BlockStatus, Member, StageRow } from "./types";

const fit = (text: string, px: number) => short(text, Math.max(4, Math.floor(px / 6.6)));
const KIND: Record<string, string> = { agent: "agent", orchestra: "orchestra", flow: "flow" };

type Click = () => void;

export function MemberColumn({ c, m, live, sel, onClick }: { c: Column; m: Member; live: { stage: string; waiting: string }[]; sel: boolean; onClick: Click }) {
  return (
    <g className="tm-col" data-testid="team-member" data-member={m.name} data-selected={sel || undefined} data-live={live.length || undefined} onClick={onClick} role="button" aria-label={`member ${m.name}`}>
      <title>{`${m.name}: ${m.role} in lineup ${m.lineup}${m.harness ? `, runs on ${m.harness}` : ", runs here"}\nclick for its stages`}</title>
      <rect className="tm-col-shape" x={c.x} y={c.y} width={c.w} height={c.h} rx={14} />
      <rect className="tm-col-head" x={c.x} y={c.y} width={c.w} height={HEAD - 8} rx={12} />
      <text className="tm-col-name" x={c.x + 14} y={c.y + 22}>{fit(m.name, c.w - 90)}</text>
      <text className="tm-col-sub" x={c.x + 14} y={c.y + 40}>{fit(`${m.lineup} · ${m.role}`, c.w - 28)}</text>
      {m.harness && (
        <g className="tm-harness" data-testid="team-harness-chip" transform={`translate(${c.x + c.w - 82} ${c.y + 9})`}>
          <rect width={72} height={18} rx={9} />
          <text x={36} y={13} textAnchor="middle">{fit("on " + m.harness, 66)}</text>
        </g>
      )}
      {live.slice(0, 2).map((l, i) => (
        <g key={l.stage} className="tm-agent-chip" data-testid="team-agent-chip" data-stage={l.stage} transform={`translate(${c.x + 12 + i * 96} ${c.y + 48})`}>
          <title>{l.waiting || `${m.name} works on ${l.stage}`}</title>
          <rect width={90} height={18} rx={9} />
          <circle cx={10} cy={9} r={3.5} />
          <text x={18} y={13}>{fit(l.waiting ? "waiting · " + l.stage : "at work · " + l.stage, 72)}</text>
        </g>
      ))}
    </g>
  );
}

function Diamond({ x, y, on }: { x: number; y: number; on: boolean }) {
  return (
    <g className="tm-gate" data-on={on || undefined} transform={`translate(${x} ${y})`}>
      <title>a required gate: it holds here until you accept, redo or stop</title>
      <path d="M7 0L14 7L7 14L0 7Z" />
    </g>
  );
}

export function StageNode({ b, row, sel, onClick }: { b: StageBox; row: StageRow | undefined; sel: boolean; onClick: Click }) {
  const s = b.spec;
  const state = row?.state || "pending";
  const members = row?.members?.length ? row.members : s.members;
  const lead = row?.lead || s.lead;
  const line = row?.waiting || row?.error || row?.summary || (s.trigger === "manual" ? "starts when you press Run" : `starts on ${s.trigger}`);
  const who = members.length ? `${members.join(", ")}${lead && members.length > 1 ? ` · lead ${lead}` : ""}` : s.kind === "orchestra" ? "the Orchestra's lead and workers" : s.kind === "flow" ? `flow ${s.flow || ""}` : "";
  return (
    <g className="tm-stage" data-testid="team-stage" data-stage={s.id} data-state={state} data-motion={stageMotion(state)} data-selected={sel || undefined}
       transform={`translate(${b.x} ${b.y})`} onClick={onClick} role="button" tabIndex={0} aria-label={`stage ${s.id}, ${state}`}
       onKeyDown={(e) => (e.key === "Enter" || e.key === " ") && (e.preventDefault(), onClick())}>
      <title>{`stage ${s.id} (${KIND[s.kind] || s.kind}): ${state}\ntrigger ${s.trigger}${s.gate === "required" ? ", gate required" : ""}\nclick for its row, Run and its gate`}</title>
      <rect className="tm-stage-shape" width={b.w} height={b.h} rx={10} />
      <rect className="tm-stage-pulse" width={b.w} height={b.h} rx={10} />
      <circle className="tm-stage-dot" cx={14} cy={16} r={4.5} />
      <text className="tm-stage-id" x={25} y={20}>{fit(s.id, b.w - 120)}</text>
      <text className="tm-stage-kind" x={b.w - (s.gate !== "none" ? 30 : 12)} y={19} textAnchor="end">{KIND[s.kind] || s.kind}</text>
      {s.gate !== "none" && <Diamond x={b.w - 24} y={8} on={state === "gated"} />}
      <text className="tm-stage-state" x={25} y={36}>{state}{row?.round && row.round > 1 ? ` · round ${row.round}` : ""}</text>
      <text className="tm-stage-line" x={86} y={36}>{fit(line, b.w - 98)}</text>
      <text className="tm-stage-who" x={25} y={51}>{fit(who, b.w - 90)}</text>
      {!!row?.cost_usd && <text className="tm-stage-cost" x={b.w - 12} y={51} textAnchor="end">{usd(row.cost_usd)}</text>}
    </g>
  );
}

function Glyph({ kind }: { kind: string }) {
  if (kind === "folder") return <path className="tm-glyph" d="M0 3h6l2 2h10v11H0z" />;
  if (kind === "git")
    return (
      <g className="tm-glyph">
        <circle cx={4} cy={3} r={2.4} />
        <circle cx={4} cy={15} r={2.4} />
        <circle cx={14} cy={7} r={2.4} />
        <path d="M4 5.4V12.6M14 9.4C14 13 8 12 5.6 14" fill="none" />
      </g>
    );
  return <path className="tm-glyph" d="M2 0h9l5 5v13H2zM11 0v5h5" />;
}

export function BlockNode({ b, st, kind, path, claims, sel, onClick }: { b: BlockBox; st: BlockStatus | undefined; kind: string; path: string; claims: string; sel: boolean; onClick: Click }) {
  const claim = claimState(st);
  const n = st?.holders.length || 0;
  const last = st?.last_change;
  const lastText = last ? `${last.by} ${last.op} ${last.key.replace(/^(section|file):/, "")}` : "no change yet";
  return (
    <g className="tm-block" data-testid="team-block" data-block={b.id} data-kind={kind} data-claim={claim} data-selected={sel || undefined}
       transform={`translate(${b.x} ${b.y})`} onClick={onClick} role="button" tabIndex={0} aria-label={`block ${b.id}, ${claim}`}
       onKeyDown={(e) => (e.key === "Enter" || e.key === " ") && (e.preventDefault(), onClick())}>
      <title>{`block ${b.id} (${kind}, claims ${claims}): ${path}\n${n ? `${n} holder${n === 1 ? "" : "s"}` : "nobody holds a part"}${st?.changes_count ? ` · ${st.changes_count} changes` : ""}\nclick for its holders and changes`}</title>
      <rect className="tm-block-shape" width={b.w} height={b.h} rx={8} />
      <g transform="translate(12 10)"><Glyph kind={kind} /></g>
      <text className="tm-block-id" x={38} y={22}>{fit(b.id, b.w - 90)}</text>
      <text className="tm-block-path" x={38} y={37}>{fit(`${path} · ${claims}`, b.w - 50)}</text>
      <text className="tm-block-last" data-testid="team-block-last" x={12} y={52}>{fit(lastText, b.w - 24)}</text>
      <g className="tm-badge" data-testid="team-block-badge" data-claim={claim} transform={`translate(${b.w - 34} 8)`}>
        <title>{claim === "writing" ? "someone writes here now" : claim === "held" ? "parts of it are held" : "free"}</title>
        <rect width={26} height={18} rx={9} />
        <text x={13} y={13} textAnchor="middle">{n}</text>
      </g>
    </g>
  );
}

export function EdgeView({ e, lit }: { e: Edge; lit: boolean }) {
  const marker = e.kind === "done" ? "url(#tm-arrow)" : e.kind === "change" ? "url(#tm-arrow-change)" : e.kind === "writes" ? "url(#tm-arrow-dim)" : undefined;
  const title = e.kind === "done" ? `${e.to} starts when ${e.from} is done` : e.kind === "change" ? `${e.to} starts when block ${e.from} changes and settles`
    : e.kind === "reads" ? `${e.from} reads block ${e.to}` : `${e.from} writes block ${e.to}`;
  return (
    <path className="tm-edge" data-testid="team-edge" data-kind={e.kind} data-from={e.from} data-to={e.to} data-lit={lit || undefined} d={e.d}
          markerEnd={marker} markerStart={e.kind === "reads" ? "url(#tm-arrow-read)" : undefined}>
      <title>{title}</title>
    </path>
  );
}
