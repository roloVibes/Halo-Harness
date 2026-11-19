# Studio: Auto's groups

Read this when your session runs on Auto (the default) and you want to know what the named, coloured boxes in Session's Live drawer and Agents -> 4 · Live are, why each helper got its model, or where the slot and the Open buttons take you.

Part of [Halo Studio](STUDIO.md), which lists every part. [Studio: what runs now, the glance and the alert](STUDIO-live.md) says where the run's drawing is.

## One piece of work, one box

On Auto (the default) main chooses who works. Studio draws main, then each piece of work main hands out as one box with
a name and a colour of its own: in Session's Live drawer the boxes go top to bottom, in Agents -> 4 · Live left to right
(main at the left, the groups in the column beside it). A new piece of work gets a new box under the last one; a box
already drawn does not move.

- **The name** is the few words main gave the work. When main gave none, it is the words its helpers share; else
  "Task {n}". A saved workflow that runs is its own box, named "workflow {W}", and it shows its steps; two runs of one
  workflow are two boxes.
- **Who is in it.** Helpers on the same piece of work share one box, also when main hands out more of it in a later
  reply. A helper started by a helper sits in its parent's box, with a third line "started by {who}: {task}". Each
  helper reads "{who}: {description}" over "{model} · {state}"; up to eight are shown, then "+{n} more".
- **The colour** comes from four that repeat in the order the boxes start (the fifth box takes the first colour again).
  The colour never says how the work goes: each helper's left edge says its state.

## The head of a box

The head names the work, then counts its helpers: "{k} agents · {w} working · {v} waiting · {d} done · {f} failed ·
${cost}" (a part that is zero is left out; "failed" in the colour of a fault). When every helper is done it reads "{k}
agents · all done · ${cost} · {time}". Under it, a line says which models were picked and why (for example "3 readers on
kimi-k3 for a pdf in the task").

Hover the head: its name, "Started by main at {t}", one line per helper ("{who} · {model} · {state}") and the cost. Hover
a helper: what it does, "{who} on {model}", "Why this model: ..." and its state, cost and time. Click a helper: its card,
with the same "Why this model: ..." line. Click the head: a card with a row per helper still at work (Pause, Stop,
steer) and [Open in Agents -> Live]. Hover main: its model and the agents this session can hand work to.

Main's line into a box lights while a helper in it works, then stays as a trace that weighs more the more helpers the
box had. A line into a box carries no label: the box's head names it.

## Work out of sight

When a helper starts working in a box that is wholly below what you see, the slot at the drawing's foot names it:
"↓ {name} · working", or "↓ {name} · working and {n} more below" when other boxes wait below too. Press it and that box's
head comes to the top (in Agents -> 4 · Live, into view). The slot's room is there from the first draw, sized for a long name of ordinary letters, so nothing above it moves when a name appears; a name of unusually wide letters can make it one line taller.

## The doors

- A box's card: **[Open in Agents -> Live]** opens Agents -> 4 · Live on the session, with that box's head at the top of
  the view and its border pulsing for two seconds. Pressed in Agents -> 4 · Live itself, it brings the box to the top
  there.
- An attention alert's **Open** (or a row's **O**) for a question a helper asks opens that helper's box, selected, with
  the helper's card open and the question's choices in it, in Session's Live drawer or in Agents -> 4 · Live.

## A map of your own

A session on a map of your own draws exactly as before: its boxes, its lines, its workflow blocks; no groups and no
colours of groups. Session's drawer keeps its "↓ {n} more below" slot as before, and Agents -> 4 · Live has no slot.
Groups on your own maps are planned, not in this release.
