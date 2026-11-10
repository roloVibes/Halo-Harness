// Where a block drag lands, and what that asks (3.3.16.3, docs/STUDIO-blocks.md "Drag and drop"):
//   a workflow / a template  anywhere on the canvas or the board  -> its confirm card, then the block wired to main
//   a bio                    into a square / a tier              -> it joins (a card in the tier; an agent of the square)
//   a square's agent         into another square / a tier        -> it moves there (into a tier it stays in the square too)
//                            onto the canvas's empty space       -> it leaves its square (the last one cannot)
//   main's edge handle       onto a square block                 -> the line: connect (or its When page when it has one)
// Anything else says in one line where it can go.
import { dropped as boardDropped, select, squareOf, wf } from "../workflows/store";
import type { Payload, Target } from "./drag";
import { say } from "./note";
import { offerIntoTier, offerTemplate, offerWorkflow } from "./ops";
import { offerConnect, offerJoin, offerLeave } from "./opsSquare";
import { temps } from "./templates";
import { selectBlock } from "./blockState";

export const dropTo = (p: Payload) => (t: Target): void => {
  if (!t) return;
  if (p.kind === "workflow") return t.kind === "board" ? boardDropped(p.ref) : offerWorkflow(p.ref);
  if (p.kind === "template") {
    const tp = temps.get().list.find((x) => x.name === p.name);
    if (!tp) return;
    if (tp.kind === "tier" && t.kind === "board") return say("a tier block goes on Agents -> Cast (its lineup's tiers)", "error");
    return offerTemplate(tp);
  }
  if (p.kind === "line") {
    if (t.kind !== "square") return;
    const q = squareOf(wf.get(), t.ref);
    if (q && q.when_mode !== "off") return selectBlock(t.ref), select(t.ref, "when");
    return offerConnect(t.ref);
  }
  const bio = p.bio;
  const from = p.kind === "agent" ? p.from : "";
  if (t.kind === "square") return from === t.ref ? undefined : offerJoin(t.ref, bio, from);
  if (t.kind === "tier") return offerIntoTier(t.name, bio, from);
  if (t.kind === "canvas" && from) return offerLeave(from, bio);
  say(`drop ${bio} into a block: a square's agents, or a tier box`, "error");
};
