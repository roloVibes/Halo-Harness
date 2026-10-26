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
  design: {
    terms: ["harness", "capability"],
    what: "Prototypes, pages, decks and logos made by your own apps and models. A project is a folder of artboards under ~/.halo/design/<slug>/, and every turn saves a new version.",
    steps: [
      ["Make or open a project", "The Start view names the first one; then Projects lists them all, and New project makes another."],
      ["Say what to design", "Write it in Thread and press Enter: the reply streams in as the turn works; Cancel turn stops it."],
      ["Look and compare", "Artboards: drag a card by its title (the places are saved with the project), slide back through its versions, Restore one."],
      ["Pin comments, ask for notes", "Pick Comment and click a frame to pin a note; Critique has a second model pin its own; Contrast checks text against its background; Send comments turns the pins into a turn."],
      ["Change it by hand", "Double-click a text in a prototype to edit it in place; a card's Knobs; the Design system panel's tokens and Sync; Rename, Delete or Download an artboard."],
      ["Hand it off", "Export writes a folder, HTML, PNG, SVG or PDF; Handoff bundles it for the next Halo or Claude Code session."],
      ["Use your own files", "Assets: add or drop logos and photos; click one to put its path in the message."],
      ["Render pictures", "The palette's Media commands add the ComfyUI panels to the section."],
    ],
    keys: [["Enter", "send the message (Shift+Enter: a new line)"], ["Mod+K", "Design: send, Design: cancel turn, Design: export, Design: new project"], ...PANEL_KEYS],
  },
  fleet: {
    terms: ["fleet", "hub", "harness", "capability", "mission", "part", "hand-off", "claim"],
    what: "Every Halo harness you run or joined, its sessions and every agent in them, live: what each one thinks, runs and writes, every decision that waits on you, what it all costs, and the controls to steer, pause, stop, take over or hand off any one agent.",
    steps: [
      ["See every harness", "This harness is the first box. Another machine joins with a pair code: Make a pair code on the Start view (or the palette), then halo fleet join on the other machine. People lists them all."],
      ["Answer what waits on you", "Attention is one queue of every card, gate, paused agent, spend cap and file conflict on every harness. A accepts, R denies or redoes with your text, S stops, O opens where it belongs."],
      ["Read the map", "Each session is a card, its agents a tree under it: a flowing outline works, amber waits on you, green just finished, red failed. By project shows each repo's dirty / ahead / behind; an amber dashed edge joins two agents editing one file."],
      ["Open an agent", "Click it (or J / K): Agent shows what it thinks as it types, each tool call with its result and diff, and what it hands back. Steer it with a nudge or a new task."],
      ["Pause, stop, hand off", "Pause holds it at its next step, Stop asks first. Take over gives it your brief; Hand to... passes it to another harness (a hand-off note in its repo) and stops it."],
      ["Know who can do what", "Capabilities has a spec card per harness: hardware, models, craft apps, MCP servers and their tools, skills, tags. Who can... ranks the fleet for what you need (gridcraft, a 4090, make a video) and picks the best one on the map."],
      ["Give the fleet one goal", "Mission (M): type the goal and Plan it; the hub's lead splits it into parts and gives each to the harness that can do it. The plan draws on the map, drag a part to another harness to move it, then Approve and Run; the report says who did what and what it cost per harness."],
      ["Hand-offs", "A part that depends on another reads that part's outputs and hand-back (take: all for everything it left), and a repo part starts from the earlier part's finished branch. The map labels each edge with what it carries and each repo part with its base."],
      ["Watch the whole fleet", "Activity draws a lane per live agent (5, 15 or 60 minutes, tool calls as ticks) over the merged live log. Costs ticks today's spend and holds the caps; Health is a doctor summary per harness."],
      ["Record and replay", "Record saves a session or one agent as a single HTML file that plays anywhere. Replay plays a finished session on the Roles canvas: the cards light up in the order they worked."],
      ["Come back", "After ten minutes away, While you were away sums up what happened: sessions, cost, decisions and who made them, files, errors, hand-offs."],
    ],
    keys: [...HOP_KEYS, ["P", "pause or resume the agent"], ["K", "in the Agent panel: stop it (asks first)"],
      ["M", "the Mission panel: one goal for the whole fleet"],
      ["A / R / S / O", "in Attention: accept, deny or redo (with a text), stop, open"], ["J / K", "in Attention: the next / previous row"], ...PANEL_KEYS],
  },
  team: {
    terms: ["team", "member", "block", "stage", "claim", "gate", "lineup", "harness"],
    what: "Your project's team file as one board: who works on it (members, each a part of a lineup, here or on a fleet harness), where their work lands (blocks: a file, a folder or a git tree, each with its claim ledger) and in which order (stages: an agent turn or an Orchestra run).",
    steps: [
      ["The team file", "<repo>/.halo/team.yaml (else ~/.halo/teams/<project>.team.yaml): the brief every agent reads first, the members, the blocks and the stages. The Start view's Make my first team writes it from the template; Validate checks it and runs the lineup preflight."],
      ["The blocks", "Each block keeps a ledger: who holds which part (a section, a file) and one change line per write. While a stage runs its members write only inside its write blocks; a part another member holds comes back naming the holder."],
      ["The stages", "Each stage reads and writes blocks and starts on a trigger: manual (Run), stage_done:<stage> (the edges down the right) or block_change:<block> (after a quiet settle window)."],
      ["Run", "Run next (or Run on a stage in the Inspector) starts it: its box pulses cyan, its members' columns show who is at work, the blocks it writes count their holders and the feed fills."],
      ["The gate", "A stage with a required gate stops at amber: the Inspector's gate card (and a Fleet Attention row) has its summary and the acceptance. Accept, Redo with an instruction, or Stop the run."],
      ["The next stage", "Accept marks it done: the stage_done edges light and the stages waiting on it start; a block that changes and settles starts its block_change stage. Stop ends the run; every stage not done is skipped."],
    ],
    keys: [["Enter", "on a selected stage or block: select it (Tab moves between them)"], ["Mod+K", "Team: run next stage, Team: validate, Team: stop, Team: open file"], ...PANEL_KEYS],
  },
  session: {
    terms: ["harness", "fleet", "hand-off", "gate"],
    what: "Your own session, live: the map of this harness's agents over what the chosen session costs on the left, and the whole right side one live column of every agent at work, as it happens. Fleet's panels narrowed to this harness and the session you chose, plus Live and Cost; Fleet keeps everything.",
    steps: [
      ["Open it", "/studio in a terminal session opens Studio here on that session (halo studio --session from a shell); Alt+1, the palette, Watch in Session on the Roles Live tab or a live Orchestra run, Open in Session on a map node and this harness's nodes in the rail land here too."],
      ["Watch everything at once", "Live, the right side: every agent's text, tool calls with their times and results, hand-backs and asks, in the order they happen, each line tagged with its agent and its state. Scroll up (or type a steer) to hold the view, N new rows · follow to come back; click a tag to follow one agent; the Steer box is always at the foot and names its target, the outlined row (click a row or press Tab to change it); Export saves the trace."],
      ["Read the map", "Each agent sits under the one that spawned it, its children fanned out, with its model, its cost and the tool it runs now (Bash 12s). Cyan works, amber waits on you, green just finished and fades, red failed and stays. Click an agent: its session becomes the chosen one."],
      ["Read the cost", "The spend ticks up beside its sparkline the moment the terminal's does; the context bar turns amber past 80 % and red past 95 %; the tokens, your turns and the cost per turn, and each agent's own share in one stacked bar (a finished sub-agent counts once)."],
      ["Open what you need", "Agent (its streams, Steer, Pause, Stop, Follow, Pin), Activity (the lanes and the full log) and Attention (one key each) wait as strips under Cost; Reset layout puts the arrangement back."],
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
      ["Use its templates", "Templates: Preview, Clone, Customize or Apply its lineups and bios (in Roles), and Run a workflow: Orchestra's new-run form, filled in."],
      ["Keep it healthy", "Each row counts the doctor's lines; Update shows its migration notes and what changes before anything is replaced (your changed files stay) and keeps the old version: Roll back brings it back; Remove asks first, then deletes only the pack's own files and lists what of yours stays."],
    ],
    keys: PANEL_KEYS,
  },
  setup: {
    terms: ["setup", "provider", "env file", "lineup"], // 3.3.0.0 R1: "setup", "provider" and "env file" are in the glossary
    what: "This box's setup on one page: the terminal wizard's blocks (halo init) as forms you fill in any order, each with its own Save. Every block writes the key the wizard writes in ~/.halo/config.json, the same as halo config set; keys go to the env file and are never shown back.",
    steps: [
      ["Read the strip", "The top line says what is set now: the providers set up here, the default model, the lineup, the permission mode and the terminal theme."],
      ["Pick the default model", "Default model lists the catalog of the providers set up here, grouped by provider, with what each model is best at; search, pick one, Save."],
      ["Pick the permission mode", "Permissions: auto, acceptEdits, default or plan, each with what it allows; Save writes the mode every new session starts in."],
      ["Pick the terminal theme", "Terminal theme: the colours of halo in your terminal, each swatch drawn in its own colours. Studio's dark / light switch in the header is this browser's own."],
      ["Pick the lineup", "Team: One model for everything, auto (the default) or a lineup, with its preview; Apply writes what the wizard's Team step writes. Edit in Roles opens it in Roles."],
      ["Each block saves alone", "A block's line says saved, 1 changed or problem; Revert drops your pick. A change made in a terminal (halo config set) shows here at once."],
      ["Next", "Session: start a session on the model you picked (halo in a terminal)."],
    ],
    keys: PANEL_KEYS,
  },
};
