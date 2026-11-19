"""tests.test_removed_replays -- Halo 3.6.0.3 B (Z6): replays and History left Halo, and a test keeps it so. The word
Grep of the decided text, case-insensitive:

    replay|scrubber|halo-replay|\\bHistory\\b|\\bCompare\\b|Back to now|What happened|\\bclip\\b

over the files of SCOPE, minus SKIP. SKIP is data: (a glob of the file, a regex of the line, the reason), one line per
thing that keeps its word for a reason of its own (a browser API, a CSS keyword, a wire key, a pinned test id, another
sense of the word). A skip excuses only the span its regex matches: that span is cut out of the line and the rest is
looked at again, so a word beside a kept one (`data-testid="history-report-replay" title="Replay ..."`) is still seen.
A skip that excuses nothing fails the test, so the list cannot rot.

Z4 batch 4 (this file's first scope) is Studio's UI source, halo_harness/studio/ui/src (.ts, .tsx, .css; the built
bundle is not in it). Z4 batch 5 (files 06 and 07) widened it to Halo's Python (PY_SCOPE: every string constant of
every .py under halo_harness/, the first-run pack's too, by an ast scan; docstrings and comments, which no person reads,
left out; a pack's own tests/ skipped like tests/) with its skip lines (R-B3's list, the retired-verb line of Z12, one
line per other sense); a skip's glob may be a tuple of globs. Z4 batch 6 (file 08) widened it to README.md, docs/
(not docs/harness/, plans/, CHANGELOG.md, tests/; the four dated records in DATED are skipped whole: a dated record,
not a guide), both glossaries and the first-run pack's text, and took out glossary.py's temporary line. Below the word
test: the server's and the terminal's own checks of files 06 and 07.
Run: python -m tests.test_removed_replays
"""
from __future__ import annotations

import fnmatch
import re
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from tests.helpers.runner import Ctx, new_registry, print_results, run_all  # noqa: E402

test, TESTS = new_registry()
REPO = Path(__file__).resolve().parent.parent
WORDS = re.compile(r"replay|scrubber|halo-replay|\bHistory\b|\bCompare\b|Back to now|What happened|\bclip\b", re.I)

# (a folder of the repo -- or one file --, the file patterns read in it)
SCOPE = [("halo_harness/studio/ui/src", ("*.ts", "*.tsx", "*.css")),
         # Z4 batch 6 (file 08): every line a person reads in the docs, the front page and the templates' text
         ("README.md", ("README.md",)),
         ("docs", ("*.md", "*.html", "*.txt")),
         ("halo_harness/templates/glossary", ("*.md",)),
         ("halo_harness/templates/packs/first-run", ("*.md", "*.yaml", "*.js"))]
#: not read: the harness's own design records (docs/harness/), and the four dated records in docs/ -- what they say was
#: true on their date; a person reads them as history of the project, not as a guide to Halo today
DOC_NOT = ("docs/harness/*",)
DATED = ("docs/design-review-2026-09-23.md", "docs/review-findings-m4-6.md", "docs/m4-6-brief.md",
         "docs/design/studio-instrument/CLAUDE-CODE-PROMPT.md")

UI = "halo_harness/studio/ui/src/"
# (a glob of the file, relative to the repo; a regex of the line; the reason it keeps its word)
SKIP = [
    (UI + "lib/agentsDoor.ts", r'q\.get\("replay"\)\) return \{ view: "map"',
     "Z7: an old replay link (`&replay=<id>`) picks 3 · Map; the one line that reads it"),
    (UI + "routes/agents/store.ts", r'q\.(has|delete)\("replay"\)|`&replay=<id>`',
     "Z7: where the door is read, the old link's `replay=` (and its `at=`) leaves the address, nothing said"),
    (UI + "**", r"\bhistory\.(replaceState|state)\b",
     "the browser's History API (history.replaceState drops a door's words from the address), not Halo's History"),
    (UI + "routes/session/promptDraft.ts",
     r"\bhistory\(sid\b|prompt\.history\.\$\{sid\}|its history per session|or history recall|a private window keeps no history",
     "prompt history: the Prompt box's sent prompts per session, Up / Down walk them (kept in this browser)"),
    (UI + "routes/session/PromptComposer.tsx",
     r"walk this session's history \(kept in this browser\)|import \{ history, setDraft \}|= history\(sid\)",
     "prompt history: Up / Down walk this session's sent prompts (promptDraft.ts)"),
    (UI + "routes/session/promptStore.ts", r"History \(promptDraft\.ts\)",
     "prompt history (promptDraft.ts), per session"),
    (UI + "routes/help-session.ts", r"Up / Down walk this session's history",
     "prompt history: the Prompt panel's help on its Up / Down keys"),
    (UI + "routes/session/CostComposition.tsx", r'^// history and what you typed|key: "history", label: "history"',
     "the conversation so far, a part of a prompt's composition (the wire key `history` of the session row)"),
    (UI + "routes/fleet/types.ts", r"history: number",
     "the conversation so far, a part of a prompt's composition (the wire key `history`)"),
    (UI + "styles/session.css", r'data-part="history"',
     "the composition bar's part for the conversation so far"),
    (UI + "routes/crew/builderStore.ts", r"const history = s\.msgs|conversation_id: s\.cid, history \}",
     "the builder's conversation so far, sent with each ask (`builder/ask`'s `history` key)"),
    (UI + "routes/orchestra/types.ts", r"history: LaneStep\[\]",
     "a lane's history, a wire key of a goal run's lane (each state it went through)"),
    (UI + "routes/crew/run/RunInspector.tsx", r"lane\??\.history",
     "a lane's history, a wire key of a goal run's lane"),
    (UI + "routes/fleet/pstore.ts", r"One lane's history",
     "a lane's history: each state from the moment it began"),
    (UI + "routes/fleet/AgentHistory.tsx", r'live/history',
     "the route `live/history` that Session's LAST SESSIONS list reads (Z6 names it `fleet/history`; Studio reads live/history)"),
    (UI + "routes/fleet/AgentHistory.tsx", r"\bhistory: |s\.history\b",
     "Session's LAST SESSIONS list, its field `history` in the panels' store (fleet/pstore.ts)"),
    (UI + "routes/fleet/pstore.ts", r"^\s*history: ",
     "Session's LAST SESSIONS list, the panels' store field `history` (read from live/history)"),
    (UI + "**", r"fleet-(agent-)?history(-run|-export)?\b|fa-history",
     "the test ids fleet-history-* / fleet-agent-history and the class .fa-history of Session's LAST SESSIONS list"),
    (UI + "**", r"history-report",
     "the goal run report page's test ids history-report-* (kept by batch 1; other tests pin them)"),
    (UI + "styles/model-select.css", r"clip-path",
     "the CSS property clip-path"),
    (UI + "styles/map-down.css", r"text-overflow: clip",
     "the CSS keyword text-overflow: clip (package A's file)"),
    (UI + "routes/crew/live/ReportCard.tsx", r"WHAT FAILED AND WHAT HAPPENED NEXT",
     "the report card's own heading, the same as `halo report` prints (## What failed and what happened next)"),
    (UI + "routes/crew/map/groupWords.ts", r'"compare the three reports and write the summary for the team"',
     "compare in its plain sense: BELOW_SAMPLE, the task name whose words size the hidden twin of Session's slot on Auto (b/batch08)"),
]


#: Z4 batch 5 (file 07): Halo's Python, read as a person reads it -- its string constants (an ast scan, f-string parts
#: too), docstrings and # comments left out. Not read: the modules nothing ships (a pack's own tests/, like tests/).
PY_SCOPE = "halo_harness"
PY_NOT = ("halo_harness/templates/packs/*/tests/*", "halo_harness/studio/ui/*")
PY = "halo_harness/"
SKIP += [
    # Z12: the one retired line, said by `halo replay`, `halo audit privacy --replays`, `halo report <an old file>`
    (PY + "cli_commands.py", r"halo replay \(playing a session back, re-running a turn on another model\) left Halo",
     "Z12: the one line the retired verb says (REPLAY_LEFT), word for word"),
    (PY + "cli_commands.py", r"^replay$|^left Halo in 3\.6\.0\.3 \(halo session export\)$",
     "Z12: the retired row `replay` (kind retired: in neither help nor completions) and its purpose words"),
    (PY + "cli.py", r"^replay$", "Z12: cli.py's own branch for the retired verb (it prints REPLAY_LEFT, exit 2)"),
    (PY + "audit_cli.py", r"^--replays$", "R-B10: `halo audit privacy --replays` is caught to say the retired line"),
    (PY + "live/report_card.py", r"^\.halo-replay$", "Z13: the old files' name ending, only to refuse them"),
    (PY + "live/report_card.py", r"^replays$", "Z13: <state>/replays/, read only to refuse an id found there"),
    (PY + "doctor.py", r"^replays$|^replay_leftovers$|Halo no longer opens replays",
     "R-B11 / Z14: the doctor's one line about the old saved files and its row (the folder is never deleted)"),
    (PY + "live/card_data.py", r"^halo-replay$", "Z5: the payload's \"format\" value stays as it is (tests pin it)"),
    # R-B3: not part of this cut
    ((PY + "agent/loop.py", PY + "doctor.py", PY + "providers/*", PY + "work_matrix.py"),
     r"reasoning[-_ ]replay\w*|replayed reasoning_content|reasoning_content replay|^replay$",
     "R-B3: reasoning replay in the providers (a model's reasoning sent back after a tool call; the work matrix's column)"),
    ((PY + "events.py", PY + "tui/dispatch.py"), r"^replay$",
     "R-B3: the transcript replay on resume (the controller's `replay` event)"),
    (PY + "cli.py", r"--replay-user-messages|replay_user_messages", "R-B3: --replay-user-messages (Claude Code's flag)"),
    ((PY + "templates/packs/signal/*", PY + "peers/protocol.py"), r"^replay(ed)?$",
     "R-B3: the Signal pack's and the peers' replay guards (a message sent twice is refused)"),
    ((PY + "commands/builtins.py", PY + "tui/tips.py"),
     r"it replays the launch typewriter line|Replay the launch intro|/intro replays the launch intro",
     "R-B3: /intro replays the launch intro"),
    # other senses of the words
    (PY + "agent/prompt.py", r"preserved and replayed back to you",
     "the agent's prompt: its earlier reasoning is replayed back to the model (a provider's reasoning replay)"),
    (PY + "providers/experiential.py", r"idempotency_replay_unavailable|the earlier result it would have replayed",
     "a gateway's idempotency replay (the earlier answer to the same request key), a provider's error"),
    (PY + "mcp/doctor_deep.py", r"replaying a previously-learned fix",
     "the MCP doctor's learned fix, applied again (no model call)"),
    ((PY + "mcp/doctor_deep.py", PY + "agent/prompt_lean_system.py"), r"with what happened|the result is what happened",
     "'what happened' in plain prose (a probe's evidence, a hook's result), not a drawer page's title"),
    (PY + "live/report_card_text.py", r"## What failed and what happened next",
     "the report card's own heading (the same in Studio's card: WHAT FAILED AND WHAT HAPPENED NEXT)"),
    ((PY + "tui/*", PY + "history.py", PY + "peers/projects.py"),
     r"history[:-]\w+|#history-\w+|Search prompt history|Search history \(Esc to cancel\)|"
     r"Ctrl\+R searches your prompt history|^history\.jsonl$",
     "prompt history: Ctrl+R searches it, Up / Down walk it (history.jsonl, the TUI's history search)"),
    (PY + "tui/app.py", r"^History$", "prompt history: Ctrl+R's key label in the TUI (its binding history_search)"),
    ((PY + "agent/*", PY + "commands/builtins.py", PY + "concierge.py", PY + "providers/model_card_words.py",
      PY + "ollama_steward/*", PY + "studio/builder_api.py", PY + "local_sched/*", PY + "tui/widgets/transcript.py"),
     r"^history$|prior history to summarize|session with history to digest|a file's history lives per-session|"
     r"the conversation history|session's recent history|in the history go as text|and the history were the old model's|"
     r"fits history to|folded-history",
     "the conversation so far (a prompt's part, a digest's input, the model's window, the builder's turns)"),
    ((PY + "live/card_run.py", PY + "orchestra/*", PY + "work/adapters/lane.py", PY + "templates/packs/coach/*"),
     r"^history$", "a lane's history, a wire key of a goal run's lane (each state it went through)"),
    (PY + "supervise/*", r"^history(\.jsonl)?$|one goal and its history|^\s*history:\s*$",
     "a goal's history under the supervisor (its rounds and decisions)"),
    ((PY + "audit_cli.py", PY + "privacy_commits.py", PY + "cli_commands.py"),
     r"--history|^history$|history: the owner's call|its history for private data",
     "git history: `halo audit privacy --history` scans every commit"),
    (PY + "doctor.py", r"no connect-time history recorded yet", "an MCP server's connect-time history (the doctor's timing)"),
    ((PY + "permissions.py", PY + "review/*", PY + "update.py", PY + "update_artifact.py", PY + "templates/packs/coach/*"),
     r"^Compare-Object$|default branch (was )?found to compare|overlays, compare, compose|^You compare finished work|"
     r"^compare$|^/compare/$|nothing to compare with checksums|harness and compare what each",
     "compare in other senses (PowerShell's Compare-Object, a review's base branch, a release's diff, checksums, the coach)"),
    ((PY + "media/*", PY + "providers/media_models.py"), r"/history/|^CLIP$|^clip$",
     "ComfyUI: its /history/ route and its CLIP text encoders"),
    (PY + "templates/packs/design/*", r"^history(\.jsonl)?$|render\.mp4 \(a clip\)",
     "the design pack: an artboard's edit history and a video clip"),
    (PY + "studio/live_api.py", r"live/history|halo_harness\.live\.history",
     "the live session's history route that Session and the Map read (and its module, halo_harness.live.history): it stays"),
    ((PY + "tui/*", PY + "agent/image_attach.py"), r"clip\.exe|halo-clip-|^clip-\*?$",
     "the clipboard: clip.exe and a pasted image's halo-clip- / clip- file name"),
]


#: Z4 batch 6 (file 08): README.md, docs/ and the templates' text. Each line names its files and its words.
D = "docs/"
SKIP += [
    # R-B3: not part of this cut
    ((D + "ARCHITECTURE*.md", D + "README.md", D + "DATABRICKS.md", D + "HANDBOOK.md", D + "MODELS-families.md",
      D + "MODELS-ollama.md", D + "MODELS-openai-codex.md", D + "COMMANDS-providers.md", D + "COMMANDS-health.md",
      D + "DEVELOPMENT.md", D + "TROUBLESHOOTING.md"),
     r"(is_)?[Rr]easoning[-_ ]replay\w*|replayed signature is bound|replay format, sampling|no known replay|"
     r"the same replayed message|catalog on every replay|^\s*replay; `None`|replaying whatever|-- on replay\), no|"
     r"documented replay shape|never replayed on (a later request|the wire)|replay machinery never|"
     r"tool-result message replays as|replays its own history|replaying it would need|malformed replay of its own|"
     r"a tool_use to replay",
     "R-B3: reasoning replay in the providers (a model's reasoning and messages sent back on the next request)"),
    ((D + "COMMANDS-main-io.md", D + "HANDBOOK.md"), r"--replay-user-messages", "R-B3: --replay-user-messages (Claude Code's flag)"),
    ((D + "COMMANDS-main-misc.md", D + "SLASH-COMMANDS-tui.md"), r"`/intro` replays|Replays the 2\.0\.0 launch intro|replay it into",
     "R-B3: /intro replays the launch intro"),
    ((D + "HOST.md", D + "VOICE-glasses.md"), r"(a|the) replay guard", "R-B3: the peers' and the glasses' replay guards"),
    (D + "SLASH-COMMANDS-session.md", r"replayed into a later request",
     "R-B3: the transcript replay (nothing a slash command shows is sent to the model again)"),
    # other senses of the words
    ((D + "GOVERNOR.md", D + "MODELS-experiential.md"), r"^replay, for instance|idempotency_replay_unavailable",
     "a gateway's idempotency replay (the earlier answer to the same request key)"),
    (D + "WORK.md", r"replays each engine's real|fixture history|`history`",
     "a test feeding a recorded fixture through the work states, and a lane's `history` wire key"),
    ((D + "ORCHESTRA.md", D + "SUPERVISE.md"), r'"history":|the lane\'s history|its file keeps its history',
     "a lane's history, a wire key of a goal run's lane (each state it went through)"),
    ((D + "SUPERVISE.md", D + "COMMANDS-supervise.md", D + "ARCHITECTURE-modules.md"),
     r"goal's first history line|retries, limits and history|supervise/history\.jsonl|its history lines|"
     r"supervise/history\.py` \(the history log",
     "a goal's history under the supervisor (its rounds and decisions)"),
    ((D + "PRIVACY.md", D + "COMMANDS-health.md", D + "DEVELOPMENT.md", D + "README.md", D + "REVIEW.md"),
     # lower case only: a capital History in these docs is the part of Studio that left, and must be seen
     r"--history|history[- ]rewrite|finds something in history|remove it from history|Halo's own history|"
     r"2\.0\.4-history-|narrows a history scan|repository: a history$|git history|project's (own )?(build )?history|"
     r"build[- ]history|want the history of (the first design|milestones|the milestone)|its history\) for secrets",
     "git history and this project's own history (`halo audit privacy --history`, docs/harness/, the dated records)"),
    ((D + "COMMANDS-packs.md", D + "PACKS.md", D + "EXTENSION_API.md"), r"(version )?history on disk",
     "a pack update keeps no version history on disk"),
    (D + "COMMANDS-mcp.md", r"`~/\.claude\.json` history", "Claude Code's own project history in ~/.claude.json"),
    ((D + "CONFIG.md", D + "STUDIO-session.md", D + "SLASH-COMMANDS-keys.md"),
     r"history\.jsonl|own prompt history|session's history \(kept in this browser|\(history search\)|walk prompt history",
     "prompt history: Ctrl+R searches it, Up / Down walk it (history.jsonl; Studio's Prompt box keeps its own)"),
    (D + "SLASH-COMMANDS-tui.md", r"shadow history", "/undo and /redo walk the file-edit history /rewind uses"),
    (("README.md", D + "ARCHITECTURE*.md", D + "GLOSSARY.md", "halo_harness/templates/glossary/GLOSSARY.md",
      D + "MODELS-*.md", D + "LOCAL-MODELS.md", D + "SLASH-COMMANDS-session.md", D + "STUDIO-sections.md",
      D + "STUDIO-session.md", D + "STUDIO-builder.md"),
     r"the history, tools and rules|no prior history|own history stays|from history every single time|"
     r"fits history to|history holds images|a history larger than|The history fitted|holds the history|"
     r"converted history|in the history go as text|switch fits the history|tools_schema, history|"
     r"the history were the old model's|history-less|\(`history`|· history \d|tools, history, you|"
     r"session's recent history|conversation_id, history|tool calls still in the history",
     "the conversation so far (a prompt's part, a digest's input, the model's window, the builder's turns)"),
    ((D + "ARCHITECTURE-modules.md", D + "STUDIO-live-panels.md"), r"live/history\.py|`conflicts` and `history`",
     "the live session's history route that Session and the Map read (live/history.py): it stays"),
    (D + "STUDIO-orchestra.md", r"`history-report`", "the goal run report page's test id history-report (kept by batch 1)"),
    (D + "STUDIO-agents.md",
     r"^\| `\?mode=agents&replay=<id>` \(with any `view=`\) \| the Map\. An old replay link opens the Map as it is now\. \|$",
     "Z7: an old replay link opens the Map as it is now (the door's row says so)"),
    ((D + "EXTENSION_API.md", D + "INSTALL.md", D + "MAC.md", D + "MEDIA.md", D + "MODELS-catalog.md", D + "ORCHESTRA.md",
      D + "VOICE-glasses.md"),
     r"compare release numbers|compare its hashes|Compare the two cards|compare with the committed ones|"
     r"nothing to compare it against|judge compare the deliverables|The compare\*\*|After the compare|"
     r"reference to compare an app",
     "compare in other senses (version ranges, hashes, two `halo doctor` cards, SVGs, the coach's judge)"),
    ((D + "COMMANDS-packs.md", D + "EXTENSION_API.md", D + "MODELS-cards.md", D + "PACKS.md", D + "PROVIDERS-copilot.md",
      D + "SLASH-COMMANDS-tui.md", D + "TROUBLESHOOTING.md", D + "ORCHESTRA.md"),
     r"(said with|saying|says|told) what happened|^\| What happened \| (What Halo says|The line \| What to do) \||"
     r"^\| The line starts \| What happened \| The next step \|",
     "'what happened' in plain prose (an error line's table, a status line), not a drawer page's title"),
    ((D + "COMMANDS-sessions.md", D + "GLOSSARY.md", "halo_harness/templates/glossary/GLOSSARY.md"),
     r"what failed and what happened next",
     "the report card's own heading (the same in Studio's card and in `halo report`)"),
    ((D + "SLASH-COMMANDS-tui.md", D + "TROUBLESHOOTING.md", D + "COMMANDS-sessions.md"), r"clip\.exe|`clip` on Windows",
     "the clipboard: Windows' clip.exe"),
    (D + "COMFYUI.md", r"render\.mp4` \(a clip\)", "a video clip a ComfyUI artboard renders"),
]


def _files():
    for folder, pats in SCOPE:
        root = REPO / folder
        for p in sorted(root.rglob("*")) if root.is_dir() else [root]:
            rel = p.relative_to(REPO).as_posix()
            if any(fnmatch.fnmatch(rel, g) for g in DOC_NOT) or rel in DATED:
                continue
            if p.is_file() and any(fnmatch.fnmatch(p.name, pat) for pat in pats):
                yield rel, p


def _strings(src: str) -> "list[tuple[int, str]]":
    """(line, text) of every string constant a person can read: f-string parts too; docstrings (the first statement of a
    module, class or function) left out, and comments are never constants."""
    import ast
    tree = ast.parse(src)
    docs = set()
    for node in ast.walk(tree):
        if isinstance(node, (ast.Module, ast.ClassDef, ast.FunctionDef, ast.AsyncFunctionDef)) and node.body:
            first = node.body[0]
            if isinstance(first, ast.Expr) and isinstance(first.value, ast.Constant) and isinstance(first.value.value, str):
                docs.add(id(first.value))
    return [(n.lineno, n.value) for n in ast.walk(tree)
            if isinstance(n, ast.Constant) and isinstance(n.value, str) and id(n) not in docs]


def _py_files():
    for p in sorted((REPO / PY_SCOPE).rglob("*.py")):
        rel = p.relative_to(REPO).as_posix()
        if "__pycache__" not in rel and not any(fnmatch.fnmatch(rel, g) for g in PY_NOT):
            yield rel, p


def scan_python() -> "tuple[list[str], set[int]]":
    hits: list = []
    used: set = set()
    for rel, p in _py_files():
        for n, text in _strings(p.read_text(encoding="utf-8")):
            for piece in text.splitlines() or [text]:
                if WORDS.search(piece) and WORDS.search(_left(rel, piece, used)):
                    hits.append(f"{rel}:{n}: {piece.strip()[:160]}")
    return hits, used


def _left(rel: str, line: str, used: "set[int] | None" = None) -> str:
    """The line with the span of every skip of this file cut out (a skip that cut a word is marked used)."""
    for i, (glob, rx, _why) in enumerate(SKIP):
        if not any(fnmatch.fnmatch(rel, g) for g in ((glob,) if isinstance(glob, str) else glob)):
            continue
        cut = re.sub(rx, " ", line)
        if used is not None and len(WORDS.findall(cut)) < len(WORDS.findall(line)):
            used.add(i)
        line = cut
    return line


def scan() -> "tuple[list[str], set[int]]":
    hits: list[str] = []
    used: set[int] = set()
    for rel, p in _files():
        for n, line in enumerate(p.read_text(encoding="utf-8").splitlines(), 1):
            if WORDS.search(line) and WORDS.search(_left(rel, line, used)):
                hits.append(f"{rel}:{n}: {line.strip()[:160]}")
    return hits, used


@test
def test_the_word_test_sees_what_it_must(ctx: Ctx):
    for said in ("Replay it on the map", "the scrubber", "a .halo-replay file", "in History.", "History's list", "Compare two runs",
                 "Back to now", "What happened", "Export a clip"):
        ctx.check(f"the pattern sees {said!r}", WORDS.search(said) is not None)
    for other in ("historyStore", "AgentHistory", "clipboard", "comparer", "eclipse"):
        ctx.check(f"the pattern does not see {other!r}", WORDS.search(other) is None)


@test
def test_a_skip_excuses_only_its_own_words(ctx: Ctx):
    # (a file, a line a skip of that file touches, whether a word must still be seen)
    for rel, line, seen in (
        (UI + "routes/crew/run/RunReport.tsx", '<Button data-testid="history-report-replay" title="Replay it">', True),
        (UI + "routes/crew/run/RunReport.tsx", '<Button data-testid="history-report-x" title="Replay">', True),
        (UI + "routes/fleet/AgentHistory.tsx", 'data-testid="fleet-history-replay">replay</button>', True),
        (UI + "routes/agents/store.ts", 'toast("this replay is gone"); q.delete("replay");', True),
        (UI + "routes/fleet/AgentHistory.tsx", 'title="History" onClick={() => api("live/history")}', True),
        (UI + "routes/crew/run/RunReport.tsx", '<Button data-testid="history-report-export">', False),
        (UI + "routes/fleet/AgentHistory.tsx", 'data-testid="fleet-history-export">export</button>', False),
        (UI + "routes/agents/store.ts", '    q.delete("replay");', False),
        (UI + "lib/agentsDoor.ts", '  if (word === "agents" && q.get("replay")) return { view: "map", word };', False),
    ):
        got = WORDS.search(_left(rel, line)) is not None
        ctx.check(f"{rel.rsplit('/', 1)[-1]}: {line.strip()!r} is {'a hit' if seen else 'kept'}, got {'a hit' if got else 'kept'}",
                  got == seen)


#: the five docs whose skip line excuses git history and this project's own history (lower case only)
GIT_HISTORY_DOCS = ("PRIVACY.md", "COMMANDS-health.md", "DEVELOPMENT.md", "README.md", "REVIEW.md")


@test
def test_the_git_history_skip_never_excuses_a_capital_history(ctx: Ctx):
    for name in GIT_HISTORY_DOCS:
        for line in ("Open it from History on the Map.", "It is listed in History.", "A History row opens it."):
            ctx.check(f"docs/{name}: {line!r} is a hit (History, the part of Studio that left)",
                      WORDS.search(_left(D + name, line)) is not None)


@test
def test_the_git_history_skip_still_excuses_git_history(ctx: Ctx):
    for name in GIT_HISTORY_DOCS:
        for line in ("The audit scans the git history.", "deleting it again doesn't remove it from history.",
                     "Fixing that needs a history rewrite (`git filter-repo`)", "this project's own build history"):
            ctx.check(f"docs/{name}: {line!r} is kept (git history, the project's own history)",
                      WORDS.search(_left(D + name, line)) is None)


#: 3.6.0.3 B (file 10): one probe per SKIP line, in SKIP's order -- a sentence of the removed feature (a replay, History,
#: Compare, the scrubber, What happened, a clip) put in a file of that line's glob, worded near the line's own words.
#: Every probe must be a hit: a skip line never excuses more than its own sense. Every line can be probed (none is
#: listed with a reason instead). A line with more than one probe names the judge's sentences that it once hid.
PROBES = [
    ((UI + "lib/agentsDoor.ts", 'if (q.get("replay")) return { view: "replay" };'),),
    ((UI + "routes/agents/store.ts", 'toast("this replay is gone"); q.delete("replay");'),),
    ((UI + "routes/agents/MapView.tsx", 'history.replaceState(null, "", "?replay=" + id);'),),
    ((UI + "routes/session/promptDraft.ts", "// open a past run from history"),),
    ((UI + "routes/session/PromptComposer.tsx", "<li>pick a finished session in the history strip</li>"),),
    ((UI + "routes/session/promptStore.ts", "// History (the Map's list of past runs)"),),
    ((UI + "routes/help-session.ts", '"Up / Down walk this session\'s history; Replay plays it back"'),),
    ((UI + "routes/session/CostComposition.tsx", '{ key: "replay", label: "history of past runs" },'),
     (UI + "routes/session/CostComposition.tsx", "// open a past run from history")),
    ((UI + "routes/fleet/types.ts", "  replayable: boolean; // shown in History"),),
    ((UI + "styles/session.css", ".history-row { display: flex; }"),),
    ((UI + "routes/crew/builderStore.ts", "// open a past run from history"),),
    ((UI + "routes/orchestra/types.ts", "  replay?: string; // its saved replay"),),
    ((UI + "routes/crew/run/RunInspector.tsx", "<Button>Replay this lane</Button>"),),
    ((UI + "routes/fleet/pstore.ts", "// One run's history, opened from History"),),
    ((UI + "routes/fleet/AgentHistory.tsx", 'api("live/replay")'),),
    ((UI + "routes/fleet/AgentHistory.tsx", 'data-testid="fleet-history-replay">replay</button>'),),
    ((UI + "routes/fleet/pstore.ts", "  replays: [], // the History list"),),
    ((UI + "routes/fleet/AgentHistory.tsx", 'data-testid="fleet-history-compare"'),),
    ((UI + "routes/crew/run/RunReport.tsx", '<Button data-testid="history-report-replay" title="Replay it">'),),
    ((UI + "styles/model-select.css", "/* clip-path for the scrubber */"),),
    ((UI + "styles/map-down.css", "/* text-overflow: clip; the clip export */"),),
    ((UI + "routes/crew/live/ReportCard.tsx", "<h3>WHAT HAPPENED</h3>"),),
    ((UI + "routes/crew/map/groupWords.ts", 'export const COMPARE = "Compare two runs side by side";'),),
    ((PY + "cli_commands.py", "halo replay plays a session back on the map"),),
    ((PY + "cli_commands.py", "replay a past session"),),
    ((PY + "cli.py", "replay <file>"),),
    ((PY + "audit_cli.py", "--replays: scan the saved replays"),),
    ((PY + "live/report_card.py", "open the .halo-replay file"),),
    ((PY + "live/report_card.py", "replays/<id>.halo-replay"),),
    ((PY + "doctor.py", "Halo opens replays from <state>/replays"),),
    ((PY + "live/card_data.py", "a halo-replay file"),),
    ((PY + "providers/openai.py", "Replay this session on another model"),),
    ((PY + "events.py", "replay the session on the map"),),
    ((PY + "cli.py", "--replay-file PATH"),),
    ((PY + "peers/protocol.py", "replayed on the map"),),
    ((PY + "tui/tips.py", "Replay the last session on the map"),),
    ((PY + "agent/prompt.py", "a past session replayed on the map"),),
    ((PY + "providers/experiential.py", "a replay of the session"),),
    ((PY + "mcp/doctor_deep.py", "replaying a past session"),),
    ((PY + "agent/prompt_lean_system.py", "What happened: the drawer page of a past run"),),
    ((PY + "live/report_card_text.py", "## What happened"),),
    ((PY + "tui/widgets/sidebar.py", "History"),),
    ((PY + "tui/app.py", "History of past runs"),),
    ((PY + "agent/loop.py", "open a past run from history"),),
    ((PY + "orchestra/run.py", "the run's replay"),),
    ((PY + "supervise/goal.py", "History of the goal runs"),),
    ((PY + "audit_cli.py", "open a past run from history"),),
    ((PY + "doctor.py", "no replay recorded yet"),),
    ((PY + "update.py", "Compare two runs side by side"), (PY + "review/target.py", "Compare two runs side by side")),
    ((PY + "media/comfy.py", "Export a clip of the session"),),
    ((PY + "templates/packs/design/run.py", "Export a clip of the session"),),
    ((PY + "studio/live_api.py", "live/replay"),),
    ((PY + "tui/widgets/sidebar.py", "Export a clip"),),
    ((D + "README.md", "Click on Replay to play a past session back on the Map."),
     (D + "HANDBOOK.md", "saves a session in the .halo-replay format"),
     (D + "MODELS-ollama.md", "Studio replays as it ran any past session")),
    ((D + "COMMANDS-main-io.md", "--replay FILE plays a saved session"),),
    ((D + "COMMANDS-main-misc.md", "`/replay` replays the last session"),),
    ((D + "HOST.md", "a replay of the session"),),
    ((D + "SLASH-COMMANDS-session.md", "replayed on the map"),),
    ((D + "GOVERNOR.md", "replay a past session"),),
    ((D + "WORK.md", "open its history in Studio"),),
    ((D + "ORCHESTRA.md", "Open the run from History."),),
    ((D + "SUPERVISE.md", "the goal's replay"),),
    ((D + "README.md", "Open a finished goal run from history on the Agents tab."),
     (D + "PRIVACY.md", "It is listed in history under the map.")),
    ((D + "PACKS.md", "a replay on disk"),),
    ((D + "COMMANDS-mcp.md", "the session history on the map"),),
    ((D + "STUDIO-session.md", "open a past run from history"),),
    ((D + "SLASH-COMMANDS-tui.md", "the Map's history"),),
    (("README.md", "A finished run moves to History under the map, with its report and a replay."),),
    ((D + "STUDIO-live-panels.md", "live/replay"),),
    ((D + "STUDIO-orchestra.md", "`history-report-replay`"),),
    ((D + "STUDIO-agents.md", "Open `?mode=agents&replay=<id>` to see a past session again."),),
    ((D + "MAC.md", "Compare two runs side by side"),),
    ((D + "PACKS.md", "The drawer page says What happened for a past run."),),
    ((D + "GLOSSARY.md", "What happened: the drawer page of a past run"),),
    ((D + "TROUBLESHOOTING.md", "Export a clip"),),
    ((D + "COMFYUI.md", "Export a clip of the session"),),
]


@test
def test_every_skip_line_flags_a_sentence_of_the_removed_feature_in_its_own_file(ctx: Ctx):
    ctx.check(f"one probe row per skip line: {len(PROBES)} rows, {len(SKIP)} lines", len(PROBES) == len(SKIP))
    for i, ((glob, rx, _why), probes) in enumerate(zip(SKIP, PROBES)):
        globs = (glob,) if isinstance(glob, str) else glob
        for rel, said in probes:
            ctx.check(f"SKIP {i}: the probe's file {rel} is one of the line's files {globs}",
                      any(fnmatch.fnmatch(rel, g) for g in globs))
            ctx.check(f"SKIP {i} /{rx[:60]}/: {said!r} in {rel} is a hit", WORDS.search(_left(rel, said)) is not None)


@test
def test_studio_names_no_replay_and_no_history(ctx: Ctx):
    hits, _used = scan()
    sep = "\n    "
    ctx.check(f"{len(hits)} lines name a replay, the scrubber, History, Compare, Back to now, What happened or a clip:"
              + sep + sep.join(hits[:80]), not hits)


@test
def test_the_docs_read_what_stays_and_the_scope_holds(ctx: Ctx):
    """Z6 widened (file 08): README.md, docs/ (not docs/harness/) and the templates' glossary and first-run pack are read
    line by line; the four dated records are skipped whole and must exist (a skip of a gone file would rot); README's
    old sentence about History would be a hit."""
    seen = {rel for rel, _p in _files()}
    for rel in ("README.md", "docs/GLOSSARY.md", "docs/STUDIO-map.md", "halo_harness/templates/glossary/GLOSSARY.md",
                "halo_harness/templates/packs/first-run/README.md"):
        ctx.check(f"the word test reads {rel}", rel in seen)
    ctx.check("the word test does not read docs/harness/", not any(r.startswith("docs/harness/") for r in seen))
    for rel in DATED:
        ctx.check(f"the dated record {rel} exists and is not read", (REPO / rel).is_file() and rel not in seen)
    ctx.check("docs/REPLAY.md is gone", not (REPO / "docs" / "REPLAY.md").exists())
    old = "what is going on). A finished run moves to History under the map, with its report and a replay."
    ctx.check("README's old sentence about History would be a hit", WORDS.search(_left("README.md", old)) is not None)
    hits = [h for h in scan()[0] if not h.startswith(UI)]
    sep = "\n    "
    ctx.check(f"{len(hits)} doc lines name a replay, the scrubber, History, Compare, Back to now, What happened or a clip:"
              + sep + sep.join(hits[:80]), not hits)


@test
def test_halo_python_names_no_replay_and_no_history(ctx: Ctx):
    """Z6 widened (file 07): the string constants of every .py under halo_harness/ (what a person reads in the terminal
    and the server's answers); docstrings and comments left out."""
    hits, _used = scan_python()
    sep = "\n    "
    ctx.check(f"{len(hits)} Python strings name a replay, the scrubber, History, Compare, Back to now, What happened or a clip:"
              + sep + sep.join(hits[:120]), not hits)


@test
def test_the_python_scan_reads_strings_not_docstrings_or_comments(ctx: Ctx):
    src = ('"""A module docstring about History."""\n# a comment about a replay\n'
           'def f():\n    """Its docstring: Compare."""\n    return f"see {1} in History under the map"\n'
           'X = "a clip"\n')
    got = [t for _n, t in _strings(src)]
    ctx.check(f"the f-string's part and the constant are read, no docstring, got {got}",
              any("in History under the map" in t for t in got) and "a clip" in got
              and not any("docstring" in t for t in got))


@test
def test_every_skip_line_still_matches_something(ctx: Ctx):
    _hits, used = scan()
    used |= scan_python()[1]
    idle =[f"{SKIP[i][0]} /{SKIP[i][1]}/ ({SKIP[i][2]})" for i in range(len(SKIP)) if i not in used]
    ctx.check("every skip line matches a line it keeps (a skip that matches nothing is taken out): " + "; ".join(idle), not idle)
    ctx.check("every skip line says its reason", all(len(why) > 10 for _g, _r, why in SKIP))


# ---- Z4 batch 5 (files 06 and 07): the server and the terminal ----------------------------------------------------

import contextlib  # noqa: E402
import io  # noqa: E402
import os  # noqa: E402
import tempfile  # noqa: E402

GONE = ("replay_clip", "clip_pipe", "replay_guard", "clip_chrome", "replay_file", "replay_run", "replay_facts", "compare",
        "compare_text", "timeline", "replay_private", "replay_cut")


@contextlib.contextmanager
def _scratch():
    """A scratch home (BRIDGE_TEST_HOME) and a scratch project folder as the working directory."""
    saved = {k: os.environ.get(k) for k in ("BRIDGE_TEST_HOME", "BRIDGE_STATE_DIR", "OLLAMA_HOST", "HALO_NO_UPDATER")}
    cwd = os.getcwd()
    with tempfile.TemporaryDirectory(prefix="halo-replays-left-") as d:
        os.environ.update(BRIDGE_TEST_HOME=d, OLLAMA_HOST="http://127.0.0.1:9", HALO_NO_UPDATER="1")
        os.environ.pop("BRIDGE_STATE_DIR", None)
        proj = Path(d) / "proj"
        proj.mkdir()
        os.chdir(proj)
        try:
            from halo_harness.config.paths import bridge_home
            yield Path(d), bridge_home()
        finally:
            os.chdir(cwd)
            for k, v in saved.items():
                os.environ.pop(k, None) if v is None else os.environ.__setitem__(k, v)


def _run(fn, argv) -> "tuple[int, str, str]":
    out, err = io.StringIO(), io.StringIO()
    with contextlib.redirect_stdout(out), contextlib.redirect_stderr(err):
        try:
            code = fn(argv)
        except SystemExit as e:
            code = e.code
    return int(code or 0), out.getvalue(), err.getvalue()


@test
def test_halo_replay_says_one_line_and_exits_2(ctx: Ctx):
    """Z12: `halo replay ...` is never a prompt: one line on stderr, exit 2, no session log written."""
    from halo_harness import cli
    from halo_harness.cli_commands import REPLAY_LEFT
    ctx.check(f"the line, word for word, got {REPLAY_LEFT!r}", REPLAY_LEFT == (
        "halo replay (playing a session back, re-running a turn on another model) left Halo in 3.6.0.3. "
        "To keep a session as a file: halo session export <id>"))
    with _scratch() as (root, _state):
        before = sorted(root.rglob("*.jsonl"))
        for argv in (["replay", "save", "x"], ["replay", "x", "--model", "y"], ["replay"]):
            code, out, err = _run(cli.main, argv)
            ctx.check(f"halo {' '.join(argv)}: exit 2, the line once on stderr, nothing on stdout, got {code} {out!r} {err!r}",
                      code == 2 and err == REPLAY_LEFT + "\n" and out == "")
        ctx.check("no session log was written", sorted(root.rglob("*.jsonl")) == before)


@test
def test_replay_is_a_retired_row_in_neither_help_nor_completions(ctx: Ctx):
    import importlib.util
    from halo_harness.cli_commands import BY_NAME, listed
    from halo_harness.completion_cli import SUBCOMMANDS
    ctx.check("cli_commands keeps `replay` as kind retired, with no target",
              BY_NAME["replay"].kind == "retired" and not BY_NAME["replay"].target)
    ctx.check("not in `halo --help`", "replay" not in [c.name for c in listed()])
    ctx.check("not a completion word ('report' stays)", "replay" not in SUBCOMMANDS and "report" in SUBCOMMANDS)
    for mod in ("halo_harness.replay", "halo_harness.replay_cli", "halo_harness.replay_verbs"):
        ctx.check(f"{mod} is gone", importlib.util.find_spec(mod) is None)


@test
def test_audit_privacy_replays_says_the_line(ctx: Ctx):
    """R-B10: `halo audit privacy --replays` prints the retired line and exits 2; the usage and --help stop naming it."""
    from halo_harness.audit_cli import cmd_audit
    from halo_harness.cli_commands import REPLAY_LEFT
    with _scratch():
        code, out, err = _run(cmd_audit, ["privacy", "--replays"])
        ctx.check(f"--replays: exit 2, the line on stderr, nothing scanned, got {code} {out!r} {err!r}",
                  code == 2 and err == REPLAY_LEFT + "\n" and out == "")
        code, out, _err = _run(cmd_audit, ["--help"])
        ctx.check(f"the usage has no --replays, got {out!r}", code == 0 and "--replays" not in out and "privacy" in out)
        code, out, _err = _run(cmd_audit, ["privacy", "--help"])
        ctx.check("halo audit privacy --help has no --replays", code == 0 and "--replays" not in out and "--history" in out)


@test
def test_the_replay_routes_answer_404(ctx: Ctx):
    """R-B1, L-B5, Z3: `replays/*` and `live/replay` left (studio/replays_api.py deleted whole); the card reads live/report."""
    from halo_harness.studio.api import Request, dispatch
    with _scratch() as (_root, state):
        def call(method, path, query=None, body=None):
            return dispatch(Request(method=method, path=path, query=query or {}, body=body or {}, cwd=Path.cwd(),
                                    state_dir=state, owner=True))
        for path, q in (("replays", {}), ("replays/plan", {"session": "s"}), ("replays/compare", {"a": "x", "b": "y"}),
                        ("replays/report", {"ref": "session:s"}), ("replays/x", {}), ("replays/x/clip", {}),
                        ("replays/clips/x.webp", {}), ("live/replay", {"session": "s"}), ("live/replay", {"run": "r"})):
            ctx.check(f"GET {path} {q}: 404", call("GET", path, q)[0] == 404)
        for path in ("replays/save", "replays/import", "replays/x/clip"):
            ctx.check(f"POST {path} (with the owner's proof): 404", call("POST", path, body={"session": "s"})[0] == 404)
        ctx.check("the card's own route is still there (no ref: 422)", call("GET", "live/report")[0] == 422)
    import importlib.util
    ctx.check("studio/replays_api.py is gone", importlib.util.find_spec("halo_harness.studio.replays_api") is None)


@test
def test_the_old_playback_modules_are_gone_and_nothing_names_them(ctx: Ctx):
    """R-B1 (b), Z5: the clip, its pipes, the Chrome class, the .halo-replay file code, its guard and the old modules'
    re-exports left; no .py / .ts / .tsx source names one (strings count); no `only_gets` branch is left."""
    import importlib.util
    for name in GONE:
        ctx.check(f"halo_harness.live.{name} is gone", importlib.util.find_spec(f"halo_harness.live.{name}") is None)
    names = "|".join(GONE)
    rx = re.compile(rf"halo_harness\.live\.({names})\b|from halo_harness\.live import [^\n]*\b({names})\b")
    me = Path(__file__).resolve()
    bad = []
    for folder in ("halo_harness", "scripts", "tools", "tests"):
        for p in (REPO / folder).rglob("*"):
            rel = p.relative_to(REPO).as_posix()
            if (p.suffix not in (".py", ".ts", ".tsx") or not p.is_file() or p.resolve() == me or "__pycache__" in rel
                    or rel.startswith("build/") or ".egg-info" in rel or "/node_modules/" in rel):
                continue
            text = p.read_text(encoding="utf-8", errors="replace")
            bad += [f"{rel}: {m.group(0)}" for m in rx.finditer(text)]
            if folder == "halo_harness" and "only_gets" in text:
                bad.append(f"{rel}: only_gets")
    ctx.check(f"no source names an old module, got {bad[:12]}", not bad)


@test
def test_the_doctor_names_the_old_folder_and_never_deletes_it(ctx: Ctx):
    """R-B11, Z14: one WARN with its fix while <state>/replays/ exists (clips counted, the home as ~); no row otherwise;
    the folder and its files are left as they were."""
    from halo_harness import doctor
    with _scratch() as (_root, state):
        ctx.check("no replays/ folder: no row", doctor._check_replay_leftovers(state) is None)
        folder = state / "replays"
        (folder / "clips").mkdir(parents=True)
        for rel in ("a.halo-replay", "b.halo-replay", "clips/a-0-5.webp"):
            (folder / rel).write_text("x", encoding="utf-8")
        line = doctor._check_replay_leftovers(state) or ""
        want = f"~{os.sep}{state.name}{os.sep}replays{os.sep}"
        ctx.check(f"one WARN: no longer opens replays, 3 files, the folder with ~, its fix, got {line!r}",
                  line.startswith(doctor.WARN) and "Halo no longer opens replays; 3 saved files are in " in line
                  and want in line and "(clips counted)" in line and line.endswith("-> fix: delete the folder when you like")
                  and "\n" not in line)
        ctx.check("the doctor's own rows carry it", "replay_leftovers" in (REPO / "halo_harness" / "doctor.py").read_text(encoding="utf-8"))
        ctx.check("nothing moved or deleted", sorted(p.relative_to(folder).as_posix() for p in folder.rglob("*") if p.is_file())
                  == ["a.halo-replay", "b.halo-replay", "clips/a-0-5.webp"])


if __name__ == "__main__":
    ctx = Ctx()
    results, passed, failed, skipped = run_all(TESTS, ctx)
    sys.exit(print_results(results, passed, failed, skipped, label="removed replays"))
