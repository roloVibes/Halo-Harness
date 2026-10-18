"""halo_harness.tui.dialogs.bio_view_text -- what the read-only bio view
(agent_bio_editor.py) prints for each field (Halo 3.1.1.0 R3; the helpers came
from the 2.0.5 bio form).

`FIELDS` is the view's field list, section by section, the same fields
Studio's bio form edits (routes/roles/BioForm.tsx); `field_rows(raw,
parent)` turns a bio's own file (and, for a bio that `extends` another, the
parent's resolved fields) into `(section, label, value, help, inherited)`
rows. `rule_sentence`, `duration_hint` and `budget_hint` render a rules line,
a timeout and a budget as plain words beside the value.
"""

from __future__ import annotations

import re
from typing import Optional

from halo_harness.field_help import bio_line

# (section, key, label); the identity fields come first and never inherit.
IDENTITY_FIELDS = (("description", "Description"), ("kind", "Kind"), ("tags", "Tags"), ("extends", "Extends"))
FIELDS = (
    ("models", "preference", "Preferred model"), ("models", "fallback", "Fallback model"),
    ("models", "effort", "Effort"), ("models", "thinking", "Thinking"),
    ("models", "context_budget", "Context budget"),
    ("tools", "allow", "Allow"), ("tools", "deny", "Deny"), ("tools", "mcp_servers", "MCP servers"),
    ("tools", "permission_mode", "Permission mode"), ("tools", "rules", "Rules"),
    ("context", "files", "Files"), ("context", "skills", "Skills"), ("context", "memory", "Memory namespace"),
    ("context", "prompt_notes", "Prompt notes"),
    ("limits", "max_iterations", "Max iterations"), ("limits", "timeout", "Timeout"),
    ("limits", "max_budget_usd", "Max budget (USD)"), ("limits", "concurrency", "Concurrency"),
    ("output", "handoff", "Hand-back"), ("output", "report_to", "Report to"),
    ("environment", "worktree", "Own git worktree"), ("environment", "offline", "Offline"),
    ("acceptance", "prompt", "Acceptance prompt"), ("acceptance", "expect", "Acceptance expect"),
    ("schedule", "cron", "Cron"), ("schedule", "every", "Every"), ("schedule", "prompt", "Prompt"),
    ("schedule", "model", "Model"),
)
SECTIONS = ("models", "tools", "context", "limits", "output", "environment", "acceptance", "schedule")

_DURATION_RE = re.compile(r"^(\d+)\s*([smhd])$")


def parse_duration_word(text: str) -> "Optional[int]":
    """`"20m"`/`"2h"`/`"90s"`/`"1d"` -> whole seconds; `None` for anything else (never raises)."""
    text = (text or "").strip().lower()
    m = _DURATION_RE.match(text) if text else None
    if not m:
        return None
    return int(m.group(1)) * {"s": 1, "m": 60, "h": 3600, "d": 86400}[m.group(2)]


def duration_hint(text: str) -> str:
    text = (text or "").strip()
    if not text:
        return ""
    seconds = parse_duration_word(text)
    if seconds is None:
        return f"{text!r} is not a recognized duration word (expected e.g. 20m, 2h, 90s, 1d) -- kept as typed."
    if seconds >= 3600:
        return f"= {seconds / 3600:.2g} hour(s)."
    if seconds >= 60:
        return f"= {seconds / 60:.2g} minute(s)."
    return f"= {seconds} second(s)."


def rule_sentence(line: str) -> str:
    """One `tools.rules` line (`deny Bash(git push*)`) as a plain sentence ("Bash may not run git push"),
    or the raw line plus its parse error."""
    from halo_harness.permissions import parse_rule
    line = (line or "").strip()
    if not line:
        return ""
    parts = line.split(None, 1)
    action = parts[0].lower() if parts and parts[0].lower() in ("deny", "ask", "allow") else None
    rest = parts[1] if action and len(parts) > 1 else line
    rule = parse_rule(rest, action=action)
    if rule.kind == "invalid":
        return f"{line!r}: {rule.error}"
    verb = {"deny": "may not run", "ask": "asks before running", "allow": "may run"}.get(action, "matches")
    if rule.kind == "bare":
        return f"{rule.tool} {verb.replace('run', 'do anything')}."
    value = (rule.value or "").rstrip("* ").strip() or (rule.value or "")
    return f"{rule.tool} {verb} {value}."


def budget_hint(max_budget_usd: "Optional[str]", model_ref: str, models: "list[dict]") -> str:
    """"about N turns at this model's price": a rough estimate (~3000 input + 600 output tokens per
    turn) against the model's catalog price; blank when the budget, the model or its price is unknown."""
    try:
        budget = float(max_budget_usd) if str(max_budget_usd or "").strip() else None
    except ValueError:
        return ""
    if budget is None or budget <= 0 or not model_ref:
        return ""
    row = next((m for m in models if isinstance(m, dict) and m.get("ref") == model_ref), None)
    price_in, price_out = (row or {}).get("price_in_per_m"), (row or {}).get("price_out_per_m")
    if not isinstance(price_in, (int, float)) or not isinstance(price_out, (int, float)):
        return ""
    per_turn = (3000 * price_in + 600 * price_out) / 1_000_000
    return f"about {budget / per_turn:.0f} turn(s) at this model's price (rough estimate)." if per_turn > 0 else ""


def _text(key: str, value) -> str:
    if value is None or value == "" or value == [] or value == {}:
        return ""
    if key == "memory" and isinstance(value, dict):
        return str(value.get("namespace") or "") if value.get("enabled", True) else "(off)"
    if isinstance(value, bool):
        return "yes" if value else "no"
    if isinstance(value, list):
        return ", ".join(str(v) for v in value)
    return str(value)


def field_rows(raw: dict, parent: "Optional[dict]" = None) -> "list[tuple[str, str, str, str, bool]]":
    """`(section, label, value, help, inherited)` for every identity field and every field of FIELDS;
    a field the bio does not set shows its parent's value (inherited) or '' (unset)."""
    rows = []
    for key, label in IDENTITY_FIELDS:
        rows.append(("identity", label, _text(key, raw.get(key)), bio_line(key), False))
    for section, key, label in FIELDS:
        own = (raw.get(section) or {}) if isinstance(raw.get(section), dict) else {}
        theirs = ((parent or {}).get(section) or {}) if isinstance((parent or {}).get(section), dict) else {}
        inherited = key not in own and key in theirs
        value = own.get(key) if key in own else theirs.get(key)
        rows.append((section, label, _text(key, value), bio_line(section, key), inherited))
    return rows


def trigger_lines(raw: dict) -> "list[str]":
    """One line per trigger: `file_change: src/**, docs/** -> <prompt>`."""
    out = []
    for t in raw.get("triggers") or []:
        if not isinstance(t, dict):
            continue
        what = {"file_change": ", ".join(t.get("paths") or []), "event": t.get("name") or "",
                "message": f"from {t.get('from') or '?'}"}.get(t.get("on"), "")
        out.append(f"{t.get('on') or '?'}: {what}" + (f" -> {t['prompt']}" if t.get("prompt") else ""))
    return out
