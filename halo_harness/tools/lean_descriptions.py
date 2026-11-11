"""halo_harness.tools.lean_descriptions -- Halo 3.3.16.1 "the local prompt diet": the short description
every built-in tool goes out with on the lean profile (a local model, or a window under 64k).

One table, beside the tools' own long descriptions (which stay for a large-window model): per tool the
one or two sentences a model needs to call it right, and a one-line meaning per parameter. A parameter
the table does not name keeps no description (its name says it); nested schemas keep their shape and
enums but lose their descriptions. tests/test_prompt_diet.py fails when a built-in tool has no entry.

    lean_definition(defn) -> defn    the wire copy of one tool definition, lean (unknown tools unchanged)
    has_lean(name) -> bool
"""

from __future__ import annotations

_AGENT = ("Launch a sub-agent for a multi-step task: a 3-5 word `description` and a self-contained `prompt` (it "
          "has no memory of this conversation). `model` or `role` picks its model; `run_in_background` reports "
          "back later as a notice; `task_id` resumes an earlier one; `count` copies or `batch` items run several "
          "in parallel (not with `run_in_background`).")
_AGENT_PARAMS = {"description": "3-5 words", "prompt": "the whole task", "subagent_type": "agent definition (default general-purpose)",
                 "model": "model ref to run it on", "role": "a lineup role whose model it runs on",
                 "effort": "reasoning effort", "run_in_background": "do not wait for it",
                 "task_id": "resume this earlier sub-agent", "count": "run N copies of prompt",
                 "batch": "one agent per item"}
_SHELL_TAIL = "Timeout 120000 ms by default, `timeout` up to 600000."

LEAN = {
    "Agent": (_AGENT, _AGENT_PARAMS),
    "Task": (_AGENT, _AGENT_PARAMS),
    "AskUserQuestion": ("Ask the user clarifying questions with suggested options when only they can decide; "
                        "`multiSelect` when several may apply. Returns an error in print mode (no one to answer).",
                        {"questions": "each: question, header (12 chars at most), options (label), multiSelect"}),
    "Bash": ("Run a shell command (bash -lc; Git Bash on Windows). " + _SHELL_TAIL + " The working directory "
             "persists between calls; use absolute paths and quote paths with spaces. Use Read, Grep, Glob and "
             "Edit instead of cat, grep, find and sed. `run_in_background` for long commands: read them with "
             "BashOutput, stop them with TaskStop; a foreground command that times out moves to the background.",
             {"command": "the command", "description": "5-10 words on what it does", "timeout": "ms, max 600000",
              "run_in_background": "start it and return a shell_id"}),
    "BashOutput": ("New output since the last check, the status and the exit code of a background shell "
                   "(Bash run_in_background). `filter`: only lines matching a regex.",
                   {"shell_id": "the shell's id", "filter": "regex"}),
    "Edit": ("Replace exact text in a file; Read the file first. `old_string` must match the file exactly "
             "(indentation as shown after Read's line-number prefix, never the prefix) and be unique, or set "
             "`replace_all`.", {"file_path": "absolute path", "replace_all": "replace every match"}),
    "EnterPlanMode": ("Switch to plan mode: research without changing anything, then call ExitPlanMode with "
                      "your plan.", {}),
    "ExitPlanMode": ("Present your finished plan for approval: approved, you implement it; with feedback, you "
                     "keep planning.", {"plan": "markdown"}),
    "Glob": ("Find files by glob pattern (\"**/*.py\"), newest first.",
             {"path": "directory (omit for the working directory)"}),
    "Grep": ("Search file contents with a ripgrep regex (use this, never grep or rg in a shell). `output_mode`: "
             "files_with_matches (default), content or count; filter with `glob` or `type`; `multiline` for "
             "cross-line patterns; escape literal braces.",
             {"pattern": "regex", "path": "file or directory", "glob": "e.g. \"*.py\"", "type": "e.g. py, js",
              "-A": "lines after (content)", "-B": "lines before (content)", "-C": "lines around (content)",
              "head_limit": "first N results"}),
    "Media": ("Extract frames and metadata from a video or audio file with local ffmpeg; Read the frame "
              "images afterwards to look at them.", {"frames": "1-8, default 4"}),
    "NotebookEdit": ("Replace, insert or delete a cell of a .ipynb notebook (absolute path). Insert goes after "
                     "`cell_id` (or first) and needs `cell_type`; replace and delete need `cell_id`.",
                     {"edit_mode": "replace (default), insert, delete", "cell_type": "code or markdown"}),
    "PowerShell": ("Run a PowerShell command (powershell.exe -NoProfile). " + _SHELL_TAIL + " Each call is a new "
                   "process: the directory and variables do not persist.",
                   {"command": "the command", "description": "5-10 words on what it does", "timeout": "ms, max 600000"}),
    "Read": ("Read a file by absolute path: 2000 lines by default, `offset`/`limit` for a part; cat -n numbered. "
             "Reads png, jpg, gif and webp images for a model that sees.",
             {"offset": "first line (0-based)", "limit": "number of lines"}),
    "Screenshot": ("Capture the screen, a window (`title`) or a region (`rect`: x, y, w, h).", {}),
    "Skill": ("Run a packaged skill by name: returns its instructions (`args` filled in) and the files beside it.",
              {"args": "optional arguments"}),
    "TaskCreate": ("Add a task to this session's shared board (sub-agents see it; TodoWrite is your private "
                   "list). Returns its id.", {"parent": "a goal task's id"}),
    "TaskList": ("List this session's shared task board.", {}),
    "TaskStop": ("Stop a running background task or shell by its id.", {"shell_id": "deprecated: task_id"}),
    "TaskUpdate": ("Update a board task: status claimed (with `owner`) takes it and fails when someone holds it; "
                   "done or blocked reports the outcome; notes and result any time.",
                   {"owner": "your name, to claim", "result": "where the outcome is"}),
    "TodoWrite": ("Your own task list for multi-step work: each call replaces the whole list. Keep one item "
                  "in_progress; mark an item completed as soon as it is done.",
                  {"todos": "the full list; activeForm says the step as it runs (\"Running the tests\")"}),
    "ToolSearch": ("Load the schema of a tool not in your list (a deferred MCP tool, or one left out to fit "
                   "your window): \"select:<name>[,<name>]\" or keywords. Then call it by name.",
                   {"query": "select:<names> or keywords", "max_results": "default 5"}),
    "WebFetch": ("Fetch a URL (with its scheme) as plain text; same-host redirects only, cached 15 minutes, "
                 "capped at 100 KB.", {"prompt": "what to get from the page"}),
    "Workflow": ("Hand a task your model cannot take (a PDF, image, audio, video) or a plan, review or research "
                 "to an enabled workflow square: `task` self-contained, `files` as paths, `name` or `need` to "
                 "choose (else worked out).", {"need": "pdf, vision, audio, video, code, plan, research, media, "
                                                       "review, work-data"}),
    "Write": ("Write a file (absolute path), replacing an existing one: Read an existing file first. Prefer Edit "
              "for a change; no new docs or README unless asked.", {}),
    "knowledge_add": ("Save a verified `finding` (evidence: the command and its result, the file and line) or a "
                      "`decision` (why, and the alternatives) for later sessions; returns its id, cite it when "
                      "reused.", {}),
    "knowledge_search": ("Search the saved findings and decisions; cite the id of an entry you reuse.",
                         {"k": "max hits (default 5)"}),
    "copilot_ask": ("Ask the user's work Microsoft 365 Copilot about their mail, meetings, chats and files; the "
                    "answer ends with numbered citations, cite them.",
                    {"prompt": "self-contained", "files": "OneDrive or SharePoint URLs", "web": "false: work data only"}),
    "ListMcpResourcesTool": ("List the resources the MCP servers offer.", {}),
    "ReadMcpResourceTool": ("Read one MCP resource by server and uri.", {}),
    "OrchestraClaim": ("Claim the smallest unit of a shared file before you edit it (`path`, `path#function`, "
                       "`path#heading-slug`); a taken unit names its holder.", {}),
    "OrchestraRelease": ("Release a unit you claimed once your edit is written, then add an OrchestraNote.", {}),
    "OrchestraClaims": ("List this run's goal files, their units and every live claim.", {}),
    "OrchestraNote": ("Add a line to this run's log: what you changed, what the next worker should know.", {}),
}

# a dynamic tail of the long description that stays (the squares this lineup enabled)
_KEEP_TAIL = {"Workflow": (" Enabled squares:", " No square is enabled")}


def has_lean(name: str) -> bool:
    return name in LEAN


def _strip(schema):
    """A schema's shape and enums kept, its descriptions dropped (nested)."""
    if isinstance(schema, dict):
        return {k: _strip(v) for k, v in schema.items() if k != "description"}
    if isinstance(schema, list):
        return [_strip(v) for v in schema]
    return schema


def _tail(name: str, desc: str) -> str:
    for marker in _KEEP_TAIL.get(name, ()):
        at = desc.find(marker)
        if at >= 0:
            return desc[at:]
    return ""


def lean_definition(defn: dict) -> dict:
    """The lean wire copy of one Anthropic-shaped tool definition; a tool with no entry is returned as is."""
    name = defn.get("name") if isinstance(defn, dict) else None
    if name not in LEAN:
        return defn
    text, params = LEAN[name]
    schema = defn.get("input_schema") or {"type": "object", "properties": {}}
    props = schema.get("properties") or {}
    lean_props = {}
    for key, prop in props.items():
        p = _strip(prop)
        if params.get(key):
            p = {**p, "description": params[key]}
        lean_props[key] = p
    lean_schema = {k: (lean_props if k == "properties" else _strip(v)) for k, v in schema.items()}
    return {**defn, "description": text + _tail(name, str(defn.get("description") or "")), "input_schema": lean_schema}
