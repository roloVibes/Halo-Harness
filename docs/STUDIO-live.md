# Studio: what runs now, the glance and the alert

Read this when you want to know where Studio's Agents -> Live went (3.6.0.0: what runs now is the Map lit up), or you use the glance (one phone-width page) or the alert when something starts waiting on you.

Part of [Halo Studio](STUDIO.md), which lists every part. [Studio: Agents](STUDIO-agents.md) has the section's tabs and doors.

## Live went (3.6.0.0 R5)

Agents -> Live (the living canvas: the session tree, the plan drawn under it, what each agent waits on, the three zoom
levels, the groups) went in 3.6.0.0 R5. What runs now is the map your session runs on, lit up
([STUDIO-map.md](STUDIO-map.md#while-a-session-runs)): the boxes light as their agents work, the line under the Map
says in one sentence what happens and what waits on whom, "What they think and say" is the drawer beside it, and a
goal run going is a line with Open. What ran is History under the Map, with the same scrubber (Play at 1x / 4x / 16x,
Save this run's replay, Export a clip, Now; [REPLAY.md](REPLAY.md)). Session's own Map is the same lit map, smaller.
`?mode=agents&view=live` lands on the Map.

## The glance

`/?mode=glance` (3.4.1.0 R4) is ONE phone-width page of this Studio -- no rail, no panels -- for a look from across the
room or from a phone (`routes/glance/`):

- **the sentence** of what is going on now, Live's own (`narrate.ts`) over the session Live would draw (this harness's
  newest with an agent at work, else its newest); with no agent tree to read, what waits on you;
- **what waits on you**, oldest first, each with its answers as **large buttons** (the row's own allow once / deny /
  stop, approve / send back, answer ...), each saying in one line what it does; an answer that needs words opens a text
  box first, a permission's deny takes an optional reason;
- **the spend** against its cap: today's spend as the caps count it (`GET live/costs`: each harness's today from its
  records, finished sessions too -- the figure History and the Cost panel read; 3.4.1.1) for the first cap
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
Agents -> Live's attention chip, on the glance and in the alert; further finishes before your next message there keep
the one row (one alert); your next message, or **A** set aside, takes it away. The session's side:
[SUBAGENTS.md](SUBAGENTS.md#when-background-work-finishes-while-the-session-is-idle-halo-3413).

| Choice | What it does |
|---|---|
| **None** (the default) | nothing is sent |
| **This browser's notification** | the click asks THIS browser for permission, once (never on load, never on its own); then each Studio page or glance open in a browser that allowed it shows one notification per new ask; a click on it opens the ask (in Studio: Session's Attention on that row; on the glance: the row, lit) |

The line under the choices says what this browser will do: it allows it; it has not been asked (press the choice and it
asks); it blocked notifications for this page (allow them in its site settings); or it has none here (a page off
127.0.0.1 or localhost has none). Two pages in one browser show one notification (each carries the row's tag).
A second channel is one more entry of `CHANNELS` in `lib/alerts.ts`; the owner has not chosen one yet, so nothing else is
built (the signal pack's phones already get the queue's new rows as `asks` notes, [REMOTE.md](REMOTE.md#transports)).
