// What a box of the run's drawing holds besides its name (3.6.0.2 R14 R15 R17), letter for letter from truth.ts:
// - a workflow's block: its head "workflow {W} · step {i} of {n}" (running) or "workflow {W}", then EVERY step a row
//   "{i} {step} · {agent} · {model} · done | working | next | failed" (states read live from the overlay);
// - the children inside their box: saved "{agent} · {model} · {state}", made up "made up: {task, 40} · {state}" with
//   [Save as an agent] (only there); three rows, then "+{n} more" (its hover lists all). A child no line brought is
//   dashed (R17): in `--off-map` on a map of his, hover "Not on the map: {sender} started this itself"; plain on the
//   default map.
import { agentRow, blockHead, madeUpRow, moreRows, offHover, stepRow } from "./truth";
import { saveAsAgent, STATE_WORDS } from "./LitBits";
import type { Block } from "./mapTypes";
import type { Kid, Overlay } from "./overlay";
import { runningStep } from "./overlayBlocks";

const SHOWN = 3;

export function BlockFace({ block, ov }: { block: Block; ov: Overlay | null }) {
  const lit = ov?.blocks[block.workflow];
  const steps = lit?.steps.length ? lit.steps : block.steps;
  const at = lit ? runningStep({ state: lit.state, steps }) : undefined;
  return (
    <span className="mp-inner mp-block" data-testid="session-map-block-face" data-workflow={block.workflow}>
      <b className="mp-name" data-testid="session-map-block-head">{blockHead(block.workflow, at, at ? steps.length : undefined)}</b>
      {steps.map((s) => (
        <span key={s.n} className="mp-step mono" data-testid="session-map-step" data-n={s.n} data-state={s.state}>
          {stepRow(s.n, s.step, s.agent, s.model, s.state)}
        </span>
      ))}
    </span>
  );
}

const kidText = (k: Kid): string => (k.made ? madeUpRow(k.task || k.agent, STATE_WORDS[k.state]) : agentRow(k.agent, k.model, STATE_WORDS[k.state]));

export function KidRows({ kids, sid, sender }: { kids: Kid[]; sid: string; sender: string }) {
  if (!kids.length) return null;
  const more = kids.length - SHOWN;
  return (
    <span className="mp-kids" data-testid="session-map-rows">
      {kids.map((k, i) => ( // past the third, a row is kept (hidden) for "+{n} more": its hover lists them all
        <span key={k.aid} hidden={more > 0 && i >= SHOWN} className="mp-kid" data-testid="session-map-row" data-row={k.aid} data-state={k.state} data-made={k.made ? "1" : undefined}
              data-helper={k.made ? k.aid : undefined} data-unlined={k.unlined ? "1" : undefined} data-off={k.off ? "1" : undefined}
              title={k.off ? offHover(sender) : undefined}>
          <span className="mp-lit-row" data-testid="session-map-row-text">{kidText(k)}</span>
          {k.made && sid && (
            <button type="button" className="mp-link" data-testid="map-save-agent" data-hover-skip=""
                    title="Open the Agents form with an agent built from this one; nothing is saved until you press Save there"
                    onClick={(e) => { e.stopPropagation(); void saveAsAgent(sid, k.aid); }}>
              Save as an agent
            </button>
          )}
        </span>
      ))}
      {more > 0 && <span className="mp-lit-row mp-muted" data-testid="session-map-rows-more" title={kids.map(kidText).join("\n")}>{moreRows(more)}</span>}
    </span>
  );
}
