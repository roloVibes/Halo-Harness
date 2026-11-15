// One box on the map (3.6.0.0 R3, the design's "Two kinds of box"): an agent (its name, its model) or a workflow (its
// name, its steps as dots, "click to open"). Hover: a summary (what it does); click: the detail in place -- a workflow
// box lists its steps (the R2 read-out's words) with a link to the Workflows tab, never wired here; an agent box what it
// may use and how careful, with a link to the Agents tab. The connect dot sits on its right edge (on a strip box, its
// left): drag it to another box, or click it (Enter) for a list. A box grows with its text; nothing in it is cut.
// 3.6.0.0 R4b: lit, hover is a summary card (lib/hover: never by itself, never over the box's controls; the keyboard
// reaches the same facts in the drawer), the box the session waits on is outlined, a box talking to another is marked.
import type { CSSProperties } from "react";
import { useStore } from "../../../lib/store";
import { useHover } from "../../../lib/hover/useHover";
import { HoverBody } from "../../../lib/hover/HoverBody";
import { cost as money } from "../../orchestra/format";
import { waitStore } from "../live/useWaits";
import { setAgentsView } from "../../agents/store";
import { openAgent } from "../store";
import { openFlow } from "../flows/flowStore";
import { dragDot } from "./drag";
import { setHover, setPick, toggleOpen, useMap } from "./mapStore";
import type { BoxFacts, DrawBox } from "./mapTypes";
import { HelperRows, LitRows, LitSteps, STATE_WORDS, useClock } from "./LitBits";
import { openFeed } from "./feedOpen";
import { useLitNow } from "./useLit";

const CAREFUL: Record<string, string> = { "ask-changes": "asks before it changes anything", "ask-commands": "asks before commands", own: "works on its own" };

function modelWords(m?: string): string {
  return !m || m === "auto" ? "Auto: picked per task" : m;
}

function Detail({ b, facts }: { b: DrawBox; facts?: BoxFacts }) {
  const f = facts?.facts || [];
  const lit = useLitNow().ov?.steps[b.id]; // R4: a workflow box's steps lit as the step runner reports them
  if (b.kind === "workflow") {
    const steps = f[0]?.steps || [];
    return (
      <div className="mp-detail" data-testid="map-box-steps">
        {lit ? <LitSteps steps={lit} />
          : steps.map((s, i) => <span key={i} className="mp-step">{i + 1} · {s.name} <span className="mp-muted">({s.agents.join(" + ")})</span></span>)}
        <button type="button" className="mp-link" onClick={(e) => { e.stopPropagation(); setAgentsView("workflows"); void openFlow(b.names[0]); }}
                data-testid="map-open-workflow">To change the steps: open it in Workflows</button>
      </div>
    );
  }
  return (
    <div className="mp-detail" data-testid="map-box-detail">
      {f.map((a) => (
        <span key={a.name} className="mp-step">{a.name}: may use {(a.uses || []).join(", ") || "nothing"}; {CAREFUL[a.careful || ""] || a.careful}</span>
      ))}
      {!b.main && (
        <button type="button" className="mp-link" onClick={(e) => { e.stopPropagation(); setAgentsView("crew"); void openAgent(b.names[0]); }}
                data-testid="map-open-agent">Open it in Agents</button>
      )}
    </div>
  );
}

export function MapBox({ b, style, inStrip, facts, mainFacts, talking }: { b: DrawBox; style?: CSSProperties; inStrip?: boolean; facts?: BoxFacts;
                                                                   mainFacts?: { model?: string; does?: string }; talking?: boolean }) {
  const open = useMap((s) => !!s.open[b.id]);
  const L = useLitNow();
  const ob = L.ov?.boxes[b.id];
  const helper = b.helper ? L.ov?.helpers.find((h) => h.aid === b.helper) : undefined;
  const state = helper?.state || ob?.state;
  const locked = useMap((s) => s.locked);
  const hover = useMap((s) => s.hover);
  const f = facts?.facts || [];
  const steps = f[0]?.steps?.length || 0;
  const missing = f.some((x) => x.missing);
  const meta = b.main ? `${!mainFacts?.model || mainFacts.model === "auto" ? "your session's model" : mainFacts.model} · the agent you talk to`
    : b.kind === "workflow" ? `${steps} step${steps === 1 ? "" : "s"} · click to ${open ? "close" : "open"}`
    : b.names.length > 1 ? "main picks one per task" : modelWords(f[0]?.model);
  const summary = helper ? `made up for this task: ${helper.task || helper.name}` : b.main ? mainFacts?.does || "main" : b.kind === "workflow" ? f[0]?.for || b.name : f[0]?.does || b.name;
  const agentIds = helper ? [helper.aid] : ob?.agents || [];
  // R4b (R4's gap 6): the box the whole session waits on is outlined (the end of the waiting path, useWaits)
  const waited = useStore(waitStore, (s) => !!s.leaf && L.mode === "live" && agentIds.includes(s.leaf));
  const clock = useClock(state === "working" || state === "waiting" ? agentIds : [], L.now);
  // R4b: hover = a summary card (what it is, what it does now, its model and cost); click = the detail in the drawer
  const lit = L.mode !== "off" && (!!ob || !!helper);
  const models = helper ? [helper.model].filter(Boolean) : ob?.models || [];
  const hv = useHover("map", lit ? `${b.id}` : "", () => (
    <HoverBody title={`${helper ? "helper" : b.main ? "main" : b.kind} ${b.name}`} is={summary}
               rows={[["now", `${helper ? STATE_WORDS[helper.state] : ob?.doing || ""}${clock ? ` · ${clock}` : ""}`],
                      ["model", models.join(", ") || (b.main ? "the session's model" : meta)], ["cost", money(helper ? helper.cost : ob?.cost || 0)]]}
               foot="Click: what it thinks and says, its facts and controls, in the drawer" />
  ), lit);
  const click = () => {
    if (!helper) toggleOpen(b.id);
    if (L.mode !== "off") openFeed(helper ? `agent:${helper.aid}` : b.id); // lit: the click opens what they think and say, for this box
  };
  return (
    <div className="mp-box" data-map-box={b.id} data-name={b.name} data-kind={b.kind} data-ghost={b.ghost || undefined} data-new={b.isNew || undefined}
         data-open={open || undefined} data-missing={missing || undefined} data-hot={hover === b.id || undefined}
         data-state={state} data-lit={(L.mode !== "off" && (ob || helper)) ? L.mode : undefined} data-helper={helper ? helper.aid : undefined}
         data-testid="map-box" tabIndex={0} style={style} title={hv.titles ? `${b.kind} ${b.name}: ${summary}${state ? ` (${STATE_WORDS[state]})` : ""}` : undefined}
         aria-expanded={open} data-hover-pad={lit ? 34 : undefined} data-waited={waited || undefined} data-talk={talking || undefined} {...hv.props}
         onMouseEnter={() => setHover(b.id)} onMouseLeave={() => setHover("")}
         onFocus={(e) => (setHover(b.id), hv.props.onFocus?.(e))} onBlur={(e) => (setHover(""), hv.props.onBlur?.(e))}
         onClick={click} onKeyDown={(e) => { if (e.key === "Enter" && e.target === e.currentTarget) click(); }}>
      <div className="mp-inner">
      <span className="mp-kind mono">
        {b.ghost ? "new · " : ""}{b.main ? "main" : helper ? "helper" : b.kind}
        {b.kind === "workflow" && <span className="mp-dots" aria-hidden="true">{"●".repeat(Math.min(steps, 8))}</span>}
        {b.isNew && !b.ghost && <span className="mp-tag" data-testid="map-new">new</span>}
      </span>
      <b className="mp-name">{b.name}</b>
      <span className="mp-meta">{helper ? helper.model || "main's tools and mode" : missing ? "missing: make it in Agents or Workflows" : meta}</span>
      {ob && L.mode !== "off" && <LitRows ob={ob} now={L.now} />}
      {helper && <HelperRows h={helper} sid={L.session?.sid || ""} all={L.ov?.helpers || []} />}
      {open && <Detail b={b} facts={facts} />}
      </div>
      {!locked && !b.ghost && !b.helper && (
        <button type="button" className="mp-dot" data-testid="map-dot" data-from={b.id} data-strip={inStrip ? "1" : undefined}
                aria-label={`${b.name}: connect it (drag to a box, or press Enter for a list)`} title="Drag to a box to connect, or click for a list"
                onPointerDown={(e) => dragDot(e, b.id, !!inStrip)} onClick={(e) => e.stopPropagation()}
                onKeyDown={(e) => { if (e.key === "Enter" || e.key === " ") { e.preventDefault(); e.stopPropagation(); setPick(b.id); } }} />
      )}
    </div>
  );
}
