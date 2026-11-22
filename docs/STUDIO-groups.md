# Studio: Auto's groups

Read this when your session runs on Auto (the default) and you want to know what the named, coloured boxes in Session's Live drawer and Agents -> 4 · Live are, what each helper does now, why each helper got its model, or where the slot and the Open buttons take you.

Part of [Halo Studio](STUDIO.md), which lists every part. [Studio: what runs now, the glance and the alert](STUDIO-live.md) says where the run's drawing is and what a box opened in place holds.

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
  helper reads "{who}: {description}" over "{model} · {state}", its state one of "working", "waiting on you", "queued",
  "done", "stopped", "failed"; up to eight are shown, then "+{n} more".
- **The colour** comes from four that repeat in the order the boxes start (the fifth box takes the first colour again).
  The colour never says how the work goes: each helper's left edge says its state. A queued or a stopped helper has a
  calm edge: it is neither working nor done.

## What each helper does now

Under its state line every helper's box says what it does at this moment, the first that applies:

- "waiting for you · {s}" while it waits on you; "paused"; "queued · {s}" while it waits for a running helper to end;
- "stopped after {span}", "done in {span}" or "failed after {span}" once it has ended;
- "{tool} · {s}" while a tool runs (the tool's own name, as the Feed shows it);
- "thinking · {s}" while it thinks, "writing · {s}" while it writes;
- else "waiting for a model reply · {s}".

A thought is drawn in the thinking colour, waiting for you in amber. When Studio does not know since when, the words
stand alone; when it never saw a helper end, the line stays blank. Hover a helper: "Now: {whole words}"; for a queued
one "Now: queued · {s}: it starts when a running helper ends."

**The held height.** The line holds two rows from the first draw, and the state line the room of its longest words, so a
box does not grow when its words change. Words that need more (a long tool name) grow the box once, while the drawing is
not held, and it keeps that height. While the pointer rests on the drawing, and for later words that need more than the
box has, the line reads "a tool · {s}" and the whole words are in the hover.

## Main's box

On Auto main's box draws the same line while main works or waits (its whole words in the line's own tooltip), and under
it what this turn did: "This turn: started {h} helpers · used {t} tools itself" ("1 helper", "1 tool"; a part that is
zero is left out: "This turn: started {h} helpers", "This turn: used {t} tools itself"). It is blank before the first
turn and kept until your next message; its rows are held from the first draw.

Hover main: "main · {model}", "This session: started {H} helpers · used {T} tools itself" and "Told it can start:
{names}" (twelve names, then " and {n} more"). Before the session's first request the hover reads "main · {model}" and
"Can hand work to: {names}".

## The head of a box

The head names the work, then counts its helpers: "{n} agents · {w} working · {q} queued · {v} waiting on you · {d} done
· {k} stopped · {f} failed · ${cost}" ("1 agent"; "{w} working" counts running and paused helpers; a part that is zero is
left out; "{v} waiting on you" in amber, "failed" in the colour of a fault). When every helper ended done it reads "{n}
agents · all done · ${cost} · {time}". A helper you stopped keeps the counts line: "1 agent · 1 stopped", "2 agents · 1
done · 1 stopped". Under it, a line says which models were picked and why (for example "3 readers on kimi-k3 for a pdf in
the task").

Hover the head: its name, "Started by main at {t}", one line per helper ("{who} · {model} · {state}") and the cost. Hover
a helper: what it does, "{who} on {model}", "Why this model: ..." and its state, cost and time. Click a helper, or the
head: its box opens in place ([STUDIO-live.md](STUDIO-live.md#the-box-opens-in-place)), with the same "Why this model:
..." line. The head's box lists a row per helper still at work; Pause and Stop act on the row you choose.

Main's line into a box lights while a helper in it works, then stays as a trace that weighs more the more helpers the
box had. A line into a box carries no label: the box's head names it.

## Work out of sight

The slot at the drawing's foot first names a group that waits on you out of sight: "↓ {name} · waits on you" when it lies
below, "↑ {name} · waits on you" when it lies above, "{name} · waits on you · under the open box" when the open box covers
it. Else it names a working group below: "↓ {name} · working". Its tail says how many other groups lie below: " · and
{n} more groups below" (" · and 1 more group below").

A press brings the group's head to the top (in Agents -> 4 · Live, into view), or the helper that asks when the head
alone would leave it out of view. With a box open, a press first closes the box; on the "under the open box" form it
only closes it. The slot's room is there from the first draw (Session's slot keeps the room of its longest words, four
of its lines at the drawer's default width), so nothing above it moves when a name appears.

## A box rings once

A helper that starts waiting on you (amber) or fails (red) gets a ring that shakes for a third of a second; a helper that
ends done (green) and a group main hands work to (the group's colour) get a ring that fades. Nothing rings on the first
draw, out of view, under the pointer or under the open box; a box rings at most once in 4 seconds, at most four at once,
the top-most first. With reduced motion set nothing rings. Main's box never rings.

## Nothing moves under the pointer

While the pointer rests on the drawing, or a box is open, the drawing keeps its laid-out geometry. A helper that joins a
group is drawn when the pointer leaves, and its group rings then; until then the head's counts leave it out.

## The doors

- A box opened in place: **[Open in Agents -> Live]** opens Agents -> 4 · Live on the session, with that box's head at
  the top of the view and its border pulsing for two seconds. Pressed in Agents -> 4 · Live itself, it brings the box to
  the top there.
- An attention alert's **Open** (or a row's **O**) for a question a helper asks opens that helper's box, selected, with
  the helper's box open in place and the question's choices in it, in Session's Live drawer or in Agents -> 4 · Live.

## A map of your own

A session on a map of your own draws exactly as before: its boxes, its lines, its workflow blocks; no groups and no
colours of groups. Session's drawer keeps its "↓ {n} more below" slot as before, and Agents -> 4 · Live has no slot.
Only Auto draws what each helper does now, the turn line and the rings. Groups on your own maps are planned, not in this
release.
