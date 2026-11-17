// What a box of the run's drawing holds besides its name (3.6.0.2 R14 R15 R17), letter for letter from truth.ts:
// - a workflow's block: its head "workflow {W} · step {i} of {n}" (running) or "workflow {W}", then EVERY step a row
//   "{i} {step} · {agent} · {model} · done | working | next | failed" (states read live from the overlay);
// - the children inside their box: saved "{agent} · {model} · {state}", made up "made up: {task, 40} · {state}" with
//   [Save as an agent] (only there); three rows, then "+{n} under it" (its hover lists all; a press opens the Feed on the
//   `under:` page of the agent that started them: P4 batch 13); a working row keeps its tool clock (runParts.tsx). A child no line brought is
//   dashed (R17): in `--off-map` on a map of his, hover "Not on the map: {sender} started this itself"; plain on the
//   default map.
import { agentRow, blockHead, madeUpRow, moreRows, offHover, stepRow } from "./truth";
import { saveAsAgent, STATE_WORDS } from "./LitBits";
import type { Block } from "./mapTypes";
import type { Kid, Overlay } from "./overlay";
import { runningStep } from "./overlayBlocks";
import { RunCtx, ToolClock } from "./runParts";
import { useContext } from "react";

const SHOWN = 3;

/** 3.6.0.2 R29: "new {t}" on a box (and over a block's rows) a build in this session wrote. */
export function NewTag({ text }: { text: string }) {
  return <span className="mp-tag mp-new-tag mono" data-testid="session-map-new">{text}</span>;
}

export function BlockFace({ block, ov, tag }: { block: Block; ov: Overlay | null; tag?: string }) {
  const lit = ov?.blocks[block.workflow];
  const steps = lit?.steps.length ? lit.steps : block.steps;
  const at = lit ? runningStep({ state: lit.state, steps }) : undefined;
  return (
    <span className="mp-inner mp-block" data-testid="session-map-block-face" data-workflow={block.workflow}>
      <b className="mp-name" data-testid="session-map-block-head">{blockHead(block.workflow, at, at ? steps.length : undefined)}</b>
      {tag && <NewTag text={tag} />}
      {steps.map((s) => (
        <span key={s.n} className="mp-step mono" data-testid="session-map-step" data-n={s.n} data-state={s.state} data-new={tag ? "" : undefined}>
          {stepRow(s.n, s.step, s.agent, s.model, s.state)}
        </span>
      ))}
    </span>
  );
}

export const kidText = (k: Kid): string => (k.made ? madeUpRow(k.task || k.agent, STATE_WORDS[k.state]) : agentRow(k.agent, k.model, STATE_WORDS[k.state]));

export function KidRows({ kids, sid, sender }: { kids: Kid[]; sid: string; sender: string }) {
  const P = useContext(RunCtx);
  if (!kids.length) return null;
  const more = kids.length - SHOWN;
  const ps = [...new Set(kids.slice(SHOWN).map((k) => k.parent).filter(Boolean))];
  const of = ps.length === 1 ? ps[0] : "main"; // whose `under:` page lists the rows not drawn
  return (
    <span className="mp-kids" data-testid="session-map-rows">
      {kids.map((k, i) => ( // past the third, a row is kept (hidden) for "+{n} more": its hover lists them all
        <span key={k.aid} hidden={more > 0 && i >= SHOWN} className="mp-kid" data-testid="session-map-row" data-row={k.aid} data-state={k.state} data-made={k.made ? "1" : undefined}
              data-helper={k.made ? k.aid : undefined} data-unlined={k.unlined ? "1" : undefined} data-off={k.off ? "1" : undefined}
              title={k.off ? offHover(sender) : undefined}>
          <span className="mp-lit-row" data-testid="session-map-row-text">{kidText(k)}</span>
          <ToolClock aids={[k.aid]} on={k.state === "working"} />
          {k.made && sid && (
            <button type="button" className="mp-link" data-testid="map-save-agent" data-hover-skip=""
                    title="Open the Agents form with an agent built from this one; nothing is saved until you press Save there"
                    onClick={(e) => { e.stopPropagation(); void saveAsAgent(sid, k.aid); }}>
              Save as an agent
            </button>
          )}
        </span>
      ))}
      {more > 0 && (P ? (
        <button type="button" className="mp-link mp-lit-row" data-testid="session-map-rows-more" data-under={of} data-hover-skip="" title={kids.map(kidText).join("\n")}
                onClick={(e) => (e.stopPropagation(), P.under(of))}>{moreRows(more)}</button>
      ) : <span className="mp-lit-row mp-muted" data-testid="session-map-rows-more" title={kids.map(kidText).join("\n")}>{moreRows(more)}</span>)}
    </span>
  );
}
