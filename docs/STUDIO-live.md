# Studio: what runs now, the glance and the alert

Read this when you want to know where Studio's Agents -> Live went (3.6.0.0: what runs now is the Map lit up), what a box of a running session's drawing shows when you click it, or you use the glance (one phone-width page) or the alert when something starts waiting on you.

Part of [Halo Studio](STUDIO.md), which lists every part. [Studio: Agents](STUDIO-agents.md) has the section's tabs and doors.

## Live went (3.6.0.0 R5)

Agents -> Live (the living canvas: the session tree, the plan drawn under it, what each agent waits on, the three zoom
levels, the groups) went in 3.6.0.0 R5. What runs now is the map your session runs on, lit up
([STUDIO-map.md](STUDIO-map.md#while-a-session-runs-4--live)): the boxes light as their agents work, the line under the Map
says in one sentence what happens and what waits on whom, "What they think and say" is the drawer beside it, and a
goal run going is a line with Open. The Map never draws the past: a finished goal run's report is its own page
(Goal run), and a finished session is exported (the session export: Session's LAST SESSIONS rows, `halo session export
<id>`). Session's own Map is the same lit map, smaller.
`?mode=agents&view=live` lands on 4 · Live (3.6.0.2), the session's run drawn on its map.
On Auto (the default) the drawing shows each piece of work main hands out as one named, coloured group ([STUDIO-groups.md](STUDIO-groups.md)).

## The box opens in place

A click on a box of a running session's drawing (Agents -> 4 · Live and Session's Live drawer) opens that box in place.

- **Where.** In Agents -> 4 · Live a sheet 440 px wide unfolds from the box's own corner in 160 ms (its top-left at the
  box's top-left, its top-right when it would pass the view's right) and folds back into the box in 120 ms; in a view
  under 456 px it is the view less 16 wide; it is kept 8 px inside the view. In Session's drawer it sits 6 px under its
  box (6 px over it when there is no room under it; with room on neither side, at the drawer's lower end), as wide as
  the drawer less 16, and opens and closes at once. It stays where it opened and is not scaled by the zoom; while it
  is open the drawing holds still and no box under it rings. With reduced motion it comes and goes at once.
- **The head** holds still: the title and x; the state line, what its box reads at that moment; "Why this model: ...";
  what it does now, in two rows ("a tool · {s}" when the words need more).
- **One row of actions**: Pause, Stop, [Open in Agents -> Live] ("Open the map at {sender}" too on a line of an agent
  that is not on the map), and the steer box of three lines. Pause reads "Resume" while a pause you set is in place:
  from your press until you take it back, also while the helper still waits on you and has not held yet; a press on
  "Resume" takes the pause back and the button reads "Pause" again.
- **The body** is the only part that scrolls: the asks with A / R / S; a row per agent still at work (the row you choose
  is the one Pause, Stop and the steer box act on); on main's box "Told it can start: {names}" (+ " and {n} more"); and
  what the agent said last. Asks that arrive while it is open are added at the body's end. In a low window the whole
  sheet scrolls so Send stays in reach.
- **What closes it**: Escape, the x, a click outside it, a wheel or a zoom over the drawing, a press on the drawing's
  slot (which closes it first), and leaving the section. A click on another box opens that box instead; a click on the
  same box closes it.
- **Last said** is read once, when you click; the sheet opens when the answer comes, or after a second with "Reading
  what it said..." (the answer is then added at the body's end). It names whose words they are: the agent of the box
  you clicked, as its row in the sheet shows it (the name stays when you choose another row). It reads "Last said by
  {name} at {hh:mm:ss}: {text}", "Last thought by {name} at {hh:mm:ss}: {text}" when its newest words are a thought,
  "Last said by {name}: {text}" or "Last thought by {name}: {text}" with no time. When the sheet has no name for them,
  the same without it: "Last said at {hh:mm:ss}: {text}", "Last thought at {hh:mm:ss}: {text}", "Last said: {text}" or
  "Last thought: {text}". Else "Nothing said yet.", or "Could not read what it said: {error}". A long text ends where
  the session's reader cut it ("... ({n} more characters)"), and then: "The rest is in the session export: Export on
  Session's Feed, or halo session export {sid}."

**Session's drawer head holds still.** While the pointer rests on the drawing (or a sheet is open), the head of
Session's Live drawer (the truth block, the status line, [Open in Agents -> Live] and the zoom) keeps the height it had
when the hold began: a longer status line shows in the room the line already had (hover the head for the whole line)
and no box moves; once the pointer leaves, the head takes the rows it needs. The status line names a running tool in a
few words, and a tool written with raw arguments (an MCP tool's `{"seconds": 30}`) by its name alone, as its box does:
"main working on mcp__srv__slow_tool · $0.00". A built-in tool reads as before ("Bash ls -la").

### The MODEL block

A helper's sheet and main's start their body with one row: "MODEL" and a button "Change". A group's sheet has the row
of the helper you chose in it: "MODEL of {name}" and "Change"; choosing another row closes the block again, and the row
then names that helper. A group whose helpers have all finished as done (it folds to its head) lists every helper as a
row, each "ended at {hh:mm:ss}", so a helper of a folded group can still be given a model from its group's sheet.
The block is closed until you press "Change": only then does Studio read the helper's agent ("Reading this helper's
agent..." until the answer comes). The button then reads "Close", which folds the block again; what it read stays while
the sheet is open, and a sheet opened anew starts closed.

Open, it holds the picker of your models (you pick, never type) and one line that says what a pick does for this kind
of helper:

- one of your agents: "Picking a model saves it in your agent {name}: its next start uses it, in this session too,
  unless main names a model itself."
- an agent that ships with Halo: "{name} ships with Halo and Auto picks its model per task. Picking a model saves your
  own {name} on that model: its next start uses it, in this session too, unless main names a model itself."
- a general helper Auto sent to one of its cards: first "A general helper that Auto sent to its {card} card for the word
  "{word}".", then "Picking a model saves your own agent {name} on that model: helpers Auto sends to its {card} card
  start as yours from their next start, in this session too, unless main names a model itself."
- a helper built into Halo (the Judge, say): "{X} is built into Halo and has no file. Picking a model makes {name}, an
  agent of yours built from {X}, on that model: main can start {name} from now, in this session too, unless it names a
  model itself."
- a helper main made up for its task: "Main made this helper up for its task. Picking a model makes {name}, an agent of
  yours built from it, on that model: main can start {name} from now, in this session too, unless it names a model
  itself."
- no picker, the line alone: a pack's agent, "{name} comes with the pack {P}; Halo does not change it here."; a Claude
  Code agent file, "{name} is a Claude Code agent file; Halo reads it and does not change it."; an agent of yours
  deleted after the helper started, "Your agent {name} is gone: it was deleted after this helper started."

These are the forms of a session that takes a new agent at once (on Auto: [CREW-sessions.md](CREW-sessions.md#usable-at-once-auto)).
In any other session "its next start uses it, in this session too", "from their next start, in this session too" and
"from now, in this session too" read "from your next session". When a map of yours names the agent, the line adds "
Your map {M} names {name}: it uses this model from its next session." (" Your map {M} names {name}: it uses yours from
its next session." for one a pick makes).

Under it: "This helper keeps {model} until it ends." ("It ran on {model}." once it ended). A helper that is running
keeps its model until it ends; a pick counts from the next start.

- **After a pick** the block says what it did. For one of your agents: "Saved: {name} runs on {model} from its next
  start, in this session too, unless main names a model itself." when the running session took it, else "Saved: {name}
  runs on {model} from your next session.". For the others: "Made {name}, an agent of yours on {model}: main can start it
  now, unless it names a model itself." or "Made {name}, an agent of yours on {model}: main can start it from your next
  session.". A pick that could not be written: "Not saved: {error}.".
- **Undo**, while the sheet stays open: "Put back: {name} runs on {old} again." after a save, "Taken back: {name} is
  gone." after a make, or "Not undone: {name} was changed since." when the agent was changed after the pick.
- **[Edit in Agents]** on one of your agents opens it in Agents' form. **[Make it an agent]** on a shipped, routed,
  built-in or made-up helper opens Agents' form filled from it: "Built from {helper} on {model}, not saved yet: read it,
  change what you like, then Save."
- **Main's box**: "Picking a model runs /model in this session." A pick switches main: "Switched main to {model} now, as
  /model in its terminal, and saved for your next launch." for a session in a terminal, "Switched main to {model} for
  this session; not saved for your next launch." otherwise. While main is in a turn nothing is sent: "Not switched: main
  is in a turn: pick again when it ends." A pick for main has no Undo.

On Auto, how the groups are laid out, what a group's head counts and when a group folds: [STUDIO-groups.md](STUDIO-groups.md).

## The glance

`/?mode=glance` (3.4.1.0 R4) is ONE phone-width page of this Studio -- no rail, no panels -- for a look from across the
room or from a phone (`routes/glance/`):

- **the sentence** of what is going on now, Live's own (`narrate.ts`) over the session Live would draw (this harness's
  newest with an agent at work, else its newest); with no agent tree to read, what waits on you;
- **what waits on you**, oldest first, each with its answers as **large buttons** (the row's own allow once / deny /
  stop, approve / send back, answer ...), each saying in one line what it does; an answer that needs words opens a text
  box first, a permission's deny takes an optional reason;
- **the spend** against its cap: today's spend as the caps count it (`GET live/costs`: each harness's today from its
  records, finished sessions too -- the figure the report card and the Cost panel read; 3.4.1.1) for the first cap
  set of this machine's, the session's project's, else this machine's; a model Halo cannot price makes it
  `$x+`, never `$0`; none set reads **no cap set**; a cap reached says its sessions are paused;
- **the elapsed time** of that session, and **the last three events** (a tool run, a line written, an ask), newest first;
- a status word: **live**; **live figures; the feed is reconnecting** while the feed reconnects; **stale: last heard N s
  ago, reconnecting** when Studio has not answered for 15 seconds. It reconnects by itself to the same Studio (a network
  blip, the SSH forward re-made: the feed backs off and retries; the queue is read every six seconds; while Studio is
  not heard the page asks every three seconds; a page that shows again reads everything once more). A Studio that was
  **restarted** has a new key (the token is made per launch and never kept or reused): the page's asks turn from "no
  answer" to refused, and it says **Studio was restarted and has a new key: open the glance again from Studio
  (Session's ... menu -> Open the glance)** and stops asking (3.4.1.1).

Open it from **Open the glance** (the palette's View group, and Session's "..." under ELSEWHERE), `halo studio --mode
glance`, or the address itself. The dialog says what Open does, costs and writes (opens a tab; nothing; nothing), shows
this machine's address and, for a phone, either the steps and a code to scan or, plainly, that the page is
this-machine-only ([REMOTE.md](REMOTE.md#the-glance-from-a-phone)).

**What it may do.** It is the same loopback Studio with the same token, served the same page; nothing new listens and
no port is added. It reads what Studio's own page reads (`GET live`, `live/attention`, `live/caps`, an agent's tail,
`settings/values`, `/api/events`) and its one write is an answer, `POST /api/live/attention/answer`, the request
Attention's keys send, with the token AND the owner proof (`X-Halo-Owner`): since 3.4.1.0 R4 that route is an owner
route, so neither Attention nor the glance answers a card without the shell's own page
([STUDIO-security.md](STUDIO-security.md#security-model)). It calls no model.

## The alert

When something **starts** waiting on you -- a new row of the attention queue: a permission, a question, a plan, a gate,
a cap -- ONE alert by the channel you picked in **Settings -> Studio -> Alerts** (`studio.alerts`, `lib/alerts.ts`),
naming what waits and on which session ("Waiting on you: Permission: Bash", "shop on you@laptop · main"). Never one per
feed event (a card is one row however many frames say it), never for what already waited when the page opened, and rows
that land together are one alert ("and 2 more").

**Background work that finished while a session was idle** (3.4.1.3) is a row of that queue too, `background_done`
("Background work finished", the job or sub-agent and what happens next): no prompt is needed to learn it. It shows on
Session's Attention (its button counts it), on the glance and in the alert; further finishes before your next message
there keep the one row (one alert); your next message, or **A** set aside, takes it away. The session's side:
[SUBAGENTS.md](SUBAGENTS.md#when-background-work-finishes-while-the-session-is-idle-halo-3413).

| Choice | What it does |
|---|---|
| **None** (the default) | nothing is sent |
| **This browser's notification** | the click asks THIS browser for permission, once (never on load, never on its own); then each Studio page or glance open in a browser that allowed it shows one notification per new ask; a click on it opens the ask (in Studio: Session on that ask's session, its Live column on the asking agent, Attention open on that row; on the glance: the row, lit) |

The line under the choices says what this browser will do: it allows it; it has not been asked (press the choice and it
asks); it blocked notifications for this page (allow them in its site settings); or it has none here (a page off
127.0.0.1 or localhost has none). Two pages in one browser show one notification (each carries the row's tag).
A second channel is one more entry of `CHANNELS` in `lib/alerts.ts`; the owner has not chosen one yet, so nothing else is
built (the signal pack's phones already get the queue's new rows as `asks` notes, [REMOTE.md](REMOTE.md#transports)).

**Open** on an ask (3.6.0.1; 3.6.0.2) -- the alert's click, an Attention row's **O** (Session's Attention), the Live ask
card's **O** -- lands on the run's drawing with the asking agent's box selected and its box open in place (the ask's
choices, Pause, Stop, the steer box). In Agents it stays in Agents, on **4 · Live** (3.6.0.1 always went to Session); elsewhere Studio
goes to **Session**, selects the ask's session, points the Live column at the agent that asks (its agent pick), opens
its Live drawer and opens **Attention** with that row selected, so A / R / S answer it. An agent the drawing puts on no
box: the Feed opens on it with its ask, and one line says so. A row of no session keeps its own home (the Ollama
steward's note: Local -> Hosts; a Try it run: its tab; a goal's plan: its panel; a spend cap: Agents -> Map); an ask of
another machine's session opens Session's **Attention** on its row (its drawing is in that machine's Studio; 3.6.0.1
opened its agent on Agents -> Map). When the ask's session has ended a moment ago, one line says so ("This session ended
at 2:41 PM. Nothing waits on you there now."); Open is never silent.
