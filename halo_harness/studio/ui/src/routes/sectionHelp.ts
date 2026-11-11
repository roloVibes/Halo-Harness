// "How this works" for each section: what it is, five to eight numbered
// steps, the keys and (3.1.1.0 R1) the glossary words it uses, each a link
// into the Glossary (docs/GLOSSARY.md; tests/test_glossary.py checks every
// word here has a paragraph). The overlay (shell/SectionHelp.tsx) adds the
// section's panels with their `about` lines; the first-visit welcome shows
// the same. docs/STUDIO.md "How each section works" mirrors this copy.
// 3.1.6.0 R6: a section's own Alt+N line is not here: the overlay puts the
// registry's key (routes/index.tsx SECTIONS) first, so a reorder moves it.
import type { SectionId } from "../lib/store";

export type SectionHelpCopy = { what: string; steps: [string, string][]; keys: [string, string][]; terms: string[] };

const PANEL_KEYS: [string, string][] = [
  ["?", "help for the focused panel; press it again (or away from a panel) for this page"],
  ["Alt+Arrows", "move the focused panel; Alt+Shift+Arrows resizes it"],
  ["Mod+K", "every command, with its key"],
  ["Esc", "close the palette, a menu, the help or the Inspector"],
];

const HOP_KEYS: [string, string][] = [
  ["J / K", "hop to the next / previous live agent"],
  ["F", "follow it: its stream scrolls with it"],
  ["Space", "pin its stream: a mini stream stays on screen in every section"],
  ["Esc", "unpin the mini stream"],
];

export const SECTION_HELP: Record<SectionId, SectionHelpCopy> = {
  orchestra: {
    terms: ["orchestra run", "lane", "claim", "plan", "hand-off", "gate", "coach", "lineup"],
    what: "Several agents write to the same files at once and nothing is lost: a lead splits your goal into lanes, one worker per lane writes its part in its own git worktree, and a gate checks the result before it lands.",
    steps: [
      ["Write the goal", "WHAT YOU WANT, how Halo knows it is done (DONE WHEN) and when to give up (STOP WHEN), plus the files the workers share and the test the gate runs."],
      ["Press Run", "Dry run asks the lead for the split only: nothing is claimed or written."],
      ["The lead splits it into lanes", "Each lane claims a part of the files; one worker per lane builds its part in its own git worktree."],
      ["How this works: the plan", "With Review the plan before it runs on, the lead's lanes open on the plan canvas first: one box per layer, drag a lane into another box to change what it runs after, click it to edit its title, claims, bio, model and hand-offs. Every edit is checked; Approve and run starts the lanes, Reject stops the run with your reason."],
      ["Hand-offs", "A lane can wait for another (after) and take its summary, its units or a file it saved (needs); it then starts from that lane's finished head, and a lane that takes nothing sees only the goal. Lanes draws each edge with what it carries and every lane's base."],
      ["The gate checks DONE WHEN", "The parts merge one at a time, your test runs, and a part that fails goes back to its worker (up to the return cap)."],
      ["Read the report", "Every check with a tick or a cross, the finished branch and its sha, the tests, the cost and the time."],
      ["How this works: Coach", "The report's Coach tab reads the run's files and suggests what to change: a bio's prompt, model or tools, a lane's after, a gate that looped. Each card shows its evidence; Apply opens the bio, the lineup or the plan with the change filled in, and you save it there. Dismiss hides a card for that run."],
    ],
    keys: [["J / K", "focus the next / previous lane at work"], ["F", "the Log follows the newest line"], ...PANEL_KEYS],
  },
  roles: {
    terms: ["lineup", "bio", "role", "tier"],
    what: "A lineup says which agent, on which model, plays each part in your sessions, and in which tier it sits. Studio shows it as cards in tier boxes you can arrange and edit; the files are ~/.halo/teams/<name>.yaml and ~/.halo/agents/<name>.yaml.",
    steps: [
      ["Pick a lineup", "Lineups lists yours and the shipped ones (the active one is marked); New makes your own copy. Each card on the canvas is one slot: an agent bio in a role, with the model that resolves for it, its price and its context."],
      ["Give each card its bio", "Bios: click one to edit it -- its model from the table (sort by price, context or best, search, best at), Test this model, its tools, limits and output. Drag a bio onto the canvas to add a card."],
      ["Stack the tiers", "Each box is a tier: a member spawns only into the next tier down, and main sits alone in tier 0. Drag a card into another box to move it (the lineup saves); a box's label strip collapses it."],
      ["Fine-tune the sections", "Inspector: Assignment edits the selected card's slot; Lineup has delegation, routing, budget, escalation, context, permissions, pipeline, acceptance and tiers, each as a form with a YAML toggle."],
      ["Fix what Problems lists", "Every edit is checked at once: blocks stop a save or a run start (a model id its catalog does not know, a bio with no tool), warns are worth a look. Click one to select its card."],
      ["Save, then Apply", "Save writes the YAML to your scope (a shipped lineup becomes your copy); Apply makes it the lineup new sessions use. Ctrl+Z undoes any edit."],
      ["Watch it work", "While a session runs, the cards whose agents work glow; click one and the Live tab shows exactly what it types, with Steer, Pause and Stop. A finished session's replay plays back on the canvas."],
    ],
    keys: [["A", "lay the canvas out (click the canvas first)"], ["F", "fit it to the panel (with the Live tab open: follow)"], ["Arrows", "nudge the selected card"], ["Del", "remove the selected card (asks first)"],
      ["Ctrl+Z / Ctrl+Shift+Z", "undo / redo a lineup edit"], ["Mod+S", "save the lineup"], ["J / K", "the next / previous card whose agent works: its Live tab opens"], ["Space", "pin that agent's mini stream"], ...PANEL_KEYS],
  },
  agents: { // 3.3.16.0 R1: Team, Roles and Orchestra folded into one section, three views; R2: and Fleet (Live's fleet scope)
    terms: ["lineup", "bio", "tier", "orchestra run", "lane", "claim", "plan", "gate", "fleet", "hub", "harness", "mission", "part", "hand-off", "capability", "replay", "waiting path"],
    what: "Your agents in one place, three views on one switch: Cast is the lineup and its bios (which agent, on which model, plays each part, in which tier), Runs gives the lineup one goal and shows the run (the lead's plan, the lanes in their worktrees, the merge, the tests, the report and the coach; a fleet mission is a run too), and Live is what runs now, this halo's session or every machine of the fleet as a tree. Team's board is gone: a run's plan shows who owns what. The Fleet section is gone too: a machine's agents are Live's, its models Local's, pairing Setup -> Machines'.",
    steps: [
      ["Pick the view", "Cast, Runs or Live, first on the bar (C, R, L). Agents opens on Live: what runs now, or one sentence when nothing does; a door that names a view lands there. Nothing else opens on its own."],
      ["Cast: the lineup", "Cast is the plan: its bar names the lineup new sessions use, and while agents run a chip counts them and goes to Live. The canvas holds the lineup's cards in their tier boxes; Lineups, Bios, the Inspector, Problems and Models are its panels. Save writes the YAML, Apply makes it the lineup new sessions use."],
      ["Runs: give it a goal", "The goal form: what you want, when it is done, the files the workers share and the test the gate runs. With Review the plan, the lead's lanes open on the plan canvas first."],
      ["Runs: who owns what", "Each lane says what it owns (its claims: the files or parts it writes), on its plan card and in Lanes; click a lane and the claims list their holder and state."],
      ["Runs: test this lineup", "Test this lineup on the bar is the guided first run on your active lineup: its card first (the models, the cost, the time, what it writes), then Run. On Auto it waits for a lineup of your own."],
      ["Live: what runs now", "The session's agents as a tree under main, every agent 1:1 with the terminal's /agents live; a lane of a running Orchestra run hangs under its lead with its number and worktree."],
      ["Live: only what is happening", "A finished agent stays ten seconds, a failed one until you dismiss it, then they leave, and a group or a session with them. The past is in History on Live's bar (newest first: what, when, how long, cost, how it ended); a row opens it as a replay, muted under its banner; Back to now returns."],
      ["Live: the plan under it", "With Plan under it on (the default when the session's lineup has tiers or squares), the lineup's blocks are the map: main, each tier, each square, each live agent inside its block, \"not in the plan\" for one no card matches. A line's label is its when, or for a moment the last hand-off on it; hover it for the last three, click it for Conversations."],
      ["Live: what waits", "Each live box says what it waits on: you, a tool, a model reply, another agent, or nothing. The sentence under the bar says what goes on now, what waits on you first; the path to what the session waits on is a brighter hairline, and a click on the sentence centres that agent."],
      ["Live: far, mid, near", "The zoom changes what is drawn: far is the blocks alone with their counts and cost, mid the boxes, near each box with its thought and its tool's last output. The far | mid | near switch sets it; Ctrl+wheel zooms around the pointer; Fit picks the level that shows it all."],
      ["Live: this halo or the fleet", "The switch on Live's bar (F on the canvas): this halo draws one session of this machine; fleet draws every machine (pair one in Setup -> Machines), its sessions and their agents, and an open mission's parts under the machine each runs on (drag a part to another machine's box to move it). It starts on the fleet when another machine is paired."],
      ["Hover, then click", "Rest the pointer on a box (a card, an agent, a session, a machine, a lane, a square) or Tab to it: a card says what it is and does after a moment. A click opens everything in the inspector. Settings -> Studio turns the cards off."],
      ["Live: the inspector", "Nothing picked: the fleet at a glance (machines, agents at work, what waits on you, today's spend, while you were away). A machine: its summary (who, health, spend) with Specs and Spend caps one block per page. An agent: its streams, Steer, Pause, Stop, Take over, Hand to, Record. A part: its card and Open in Runs."],
      ["Attention", "The chip at the right of the bar counts every decision that waits on you across the fleet, amber while any does; it (or A) opens the queue: A accepts, R denies or redoes with your text, S stops, O opens where it belongs."],
      ["Runs: missions", "Runs' list holds this machine's runs and the fleet's missions; a mission opens its Mission panel (plan, running, report, coach). With more than one machine paired, the goal form offers Run it across the fleet."],
    ],
    keys: [["C / R / L", "Cast, Runs, Live (outside a text field)"], ["A", "the Attention queue"], ["M", "the Mission panel (Runs)"], ["F", "on the Live canvas: this halo or the fleet"],
      ["J / K", "the next / previous agent at work (Runs: the next lane)"], ...PANEL_KEYS],
  },
  session: {
    terms: ["harness", "fleet", "hand-off", "gate"],
    what: "Your own session, live: one live column of every agent at work, as it happens, fills the stage; the map of this harness's agents, what the chosen session costs and the rest wait as strips at its foot. Every machine's agents are Agents -> Live's (the fleet scope).",
    steps: [
      ["Open it", "/studio in a terminal session opens Studio here on that session (halo studio --session from a shell); Alt+1, the palette, Watch in Session on Agents' Live tab or a live run in Agents: Runs, and Open in Session on a node's menu on Agents -> Live land here too."],
      ["Watch everything at once", "Live, the whole stage: every agent's text, tool calls with their times and results, hand-backs and asks, in the order they happen, each line tagged with its agent and its state. Scroll up (or type a steer) to hold the view, N new rows · follow to come back; click a tag to follow one agent; the Steer box is always at the foot and names its target, the outlined row (click a row or press Tab to change it); Export saves the trace."],
      ["Read the map", "Each agent sits under the one that spawned it, its children fanned out, with its model, its cost and the tool it runs now (Bash 12s). Cyan works, amber waits on you, green just finished and fades, red failed and stays. Click an agent: its session becomes the chosen one."],
      ["Read the cost", "The spend ticks up beside its sparkline the moment the terminal's does; the context bar turns amber past 80 % and red past 95 %; the tokens, your turns and the cost per turn, and each agent's own share in one stacked bar (a finished sub-agent counts once)."],
      ["Open what you need", "Map, Cost, Agent (its streams, Steer, Pause, Stop, Follow, Pin), Activity (the lanes and the full log) and Attention (one key each) wait as strips at the foot; a click opens one beside Live, Reset layout puts the arrangement back."],
    ],
    keys: [...HOP_KEYS, ["P", "pause or resume the agent"], ["K", "in the Agent panel: stop it (asks first)"],
      ["Esc", "in Live: show every agent again after a tag click"], ["A / R / S / O", "in Attention, or on the newest ask card in Live: accept, deny or redo (with a text), stop, open"], ...PANEL_KEYS],
  },
  packs: {
    terms: ["pack", "lineup", "bio", "capability", "orchestra run"], // 3.2.1.0 R1: "pack" is in the glossary
    what: "The Pack Manager: find a pack in the places you trust (the folders and git urls of packs.sources, and the packs Halo ships), read what it brings and what it asks for, then install, grant, enable, set up, update or remove it. Every button runs the same code as halo pack, and every line it answers is the one the terminal prints.",
    steps: [
      ["Find a pack", "Sources lists each place a bare id is looked for, in order, with the packs it holds; Add source puts a folder or a git url in packs.sources. Click a name to read the pack before you install it."],
      ["Install it", "Install copies it into ~/.halo/packs/<id>/ (or this repo's .halo/packs/), disabled: nothing of it runs yet. It shows in Installed."],
      ["Read what it brings", "Details: its extension API and Halo ranges beside this Halo's, the packs it requires, what keeps it from running here (in the doctor's words), each permission it requests and what needs it, and everything it contributes."],
      ["Grant and enable", "Pick the permissions to grant with their toggles, then Enable: its bios, lineups, Studio section, fleet capability and workflows run from now on; a contribution whose permission you did not grant stays off."],
      ["Set it up", "Settings is the pack's own form (its config.schema): Save checks the values, then writes packs.settings.<id>."],
      ["Use its templates", "Templates: Preview, Clone, Customize or Apply its lineups and bios (in Agents: Cast), and Run a workflow: the new-run form in Agents: Runs, filled in."],
      ["Keep it healthy", "Each row counts the doctor's lines; Update shows its migration notes and what changes before anything is replaced (your changed files stay) and keeps the old version: Roll back brings it back; Remove asks first, then deletes only the pack's own files and lists what of yours stays."],
    ],
    keys: PANEL_KEYS,
  },
  setup: {
    terms: ["setup", "provider", "env file", "lineup"], // 3.3.0.0 R1: "setup", "provider" and "env file" are in the glossary
    what: "This box's setup one page at a time, the page halo init opens: the terminal wizard's steps in its order, one block per page with its own Save, then a Summary. Every block writes the key the wizard writes in ~/.halo/config.json, the same as halo config set; keys go to the env file and are never shown back. Nothing opens on its own here. halo init --terminal is the terminal wizard.",
    steps: [
      ["Follow the rail", "The rail on top lists the steps in the wizard's order: the current one lit, a done one ticked. Click any step to open its page; the line under it says what is set now."],
      ["Set a provider up", "Providers: one card per provider. Paste a key (or a host), Save & test writes it to the env file, turns the provider on and reads its model list. Ollama's finders (Find, Scan, Add, Measure) open under its card."],
      ["Point at your local models", "Local models: the folders your model files are in and the runtime that serves them (llama-server or mlx_lm). Nothing here is required."],
      ["Pick the default model", "Default model lists the catalog of the providers set up here, grouped by provider, with what each model is best at; search, pick one, Save (Enter saves too)."],
      ["Pick the permission mode", "Permissions: auto, acceptEdits, default or plan, each with what it allows; Save writes the mode every new session starts in."],
      ["Pick the theme", "Theme: one of ten palettes for halo in your terminal and for Studio, each swatch drawn in its own colours; Settings -> Themes has the modifiers and a preview."],
      ["Pick the lineup", "Team: One model for everything, auto (the default) or a lineup, with its preview; Apply writes what the wizard's Team step writes."],
      ["Run the check", "Check: doctor, the model catalog and one hello call are ticked; the quick gym and the guided first run say what they cost first. Linux fixes is a step only when this box needs them."],
      ["Read the Summary", "One row per step with what it holds and a Change jump, the last check with Run the ticked checks, and the guided first run's card."],
    ],
    keys: [
      ["Ctrl+Left / Ctrl+Right", "Back / Next (outside a text field)"],
      ["Enter", "in a block's field: that block's Save"],
      ["?", "this help"],
      ["Mod+K", "every command, with its key"],
    ],
  },
  settings: {
    terms: ["config key", "setup", "provider"], // 3.3.3.0 R2: "config key" joins the glossary
    what: "Every config key of ~/.halo/config.json, the ones halo config set and a dozen features write, one page per group: each row is one key with its help line, its value against its default, Reset to default and the exact halo config set line. A change saves at once and says when it takes effect. Nothing opens on its own here; halo settings [group] opens a group's page from a terminal.",
    steps: [
      ["Pick a group", "The rail on the left lists the groups (General, Agents and roles ... Local) with how many of their keys are set; a click opens its page."],
      ["Read a row", "Title, one help line, the control, and under it the default it falls back to and when a change takes effect: now, in the next session, or on the next launch."],
      ["Change a key", "A switch or a choice saves on the click; a number or a text saves on Enter or when you leave the field; a list or JSON saves with its Save. The row says saved and when it takes effect."],
      ["Go back to the default", "A row marked default is not in config.json. Reset to default takes a key you set back out, and the marker returns."],
      ["Keys with entries", "A key with a placeholder (a connector, a provider, an Ollama host's field) is a table of the entries saved, each with its own control and Reset; Edit as JSON writes the whole section."],
      ["Search", "The box in the page head finds a row across every group by its title, key or help line; Mod+K lists every row as Settings: <title>."],
      ["The same from a terminal", "Each row's footer is the halo config set line that does the same; halo settings --terminal lists a group's keys with their values."],
    ],
    keys: [
      ["Enter", "in a number or text field: save it"],
      ["Ctrl+Enter", "in a list or JSON box: save it"],
      ["?", "this help"],
      ["Mod+K", "every command and every Settings row"],
    ],
  },
  local: {
    terms: ["host", "steward", "profile", "fit plan", "speed card", "library", "quant"], // 3.3.5.0 R1: "host", "speed card"; R2: "library", "quant"
    what: "Everything about the machines that serve your local models and the models they serve, one page at a time: Resources (the live GPU, VRAM, RAM and CPU, and every call to a local server as it happens), Hosts (every server Halo knows, with Load, Unload and Make it fit), Models (every installed model with its card, its fit meter and the intent filter), Library (what could be installed from Ollama's library and the Hugging Face Hub, each with a fit badge), then Hugging Face, Benchmarks and Steward, which the next rounds fill. Five ideas run through every page: the fit meter, why on every number, intents not model names, make it fit, and the hub as the one picture of the network. Nothing opens on its own; halo local opens it from a terminal.",
    steps: [
      ["Pick a page", "The rail on the left lists the seven pages; a click opens one, and the page last open comes back next time."],
      ["Watch the card", "Resources: one strip per host, sampled once a second while the page is open: the VRAM bar names what holds it, the GPU line is the last minute, RAM, CPU and the temperature beside them; hover a number for its source."],
      ["Watch the calls", "Under the strips the traffic view lists every call to a local server, newest at the foot, the steward's server events between them; filter by host, model, machine or kind, and Follow keeps the newest in view."],
      ["Load and unload", "Hosts: every server as a card with what is loaded and what is installed; Load warms a model at its profile's window, Unload lets it go; a host another machine serves goes through its fleet member, as its owner allows."],
      ["Make it fit", "A host whose models do not fit its card together offers the fit plan's chosen option in one click, with Undo beside it."],
      ["Find the right model", "Models: pick what you want a model for (code, chat, long documents, images, embed) and the rows rank by fit for this card; Use as default and Make it the coder lane are one click each."],
      ["Browse the library", "Library: search Ollama's library and the Hugging Face Hub; each row's fit badge follows the host and window you pick, a click shows its other tags or files, Copy takes its pull line."],
      ["What comes next", "Hugging Face, Benchmarks and Steward say what they will hold and the commands that do that work today."],
      ["Media on ComfyUI", "The header's + menu (or the palette's Media lines) adds Media status, Media models and Workflows: each floats over the page until you close it."], // 3.3.13.0 R2: Design's before
    ],
    keys: [
      ["?", "this help"],
      ["Mod+K", "every command, Local: <page> among them"],
      ["Esc", "close the palette, a menu or the help"],
    ],
  },
};
