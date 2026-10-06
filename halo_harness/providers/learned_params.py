"""halo_harness.providers.learned_params -- Halo 2.0.5 round 3 (2.0.3-brief.md
item G1): ONE engine that plans the smallest fix for an upstream 400/422
naming a request-body field this harness itself put on the wire, generalised
from the 1.0.1 gpt-6 `reasoning_effort`-with-tools rule and the GLM/Claude
effort-field rejection (`providers.errors.is_effort_with_tools_rejected_
message`/`is_effort_rejected_message`, both left exactly as they are --
they keep their own richer semantics: "none" specifically for the gpt-6
tools case, a multi-field strip for the general effort case, both checked
in `agent/loop.py` BEFORE this module ever gets a turn). This module covers
every OTHER field the gateway can reject that neither of those checks
claims, AND picks up the effort family too when the live wording doesn't
match either narrower pattern (e.g. a bare "unknown field" 400).

Watched fields: every name 2.0.3-brief.md item G1 lists (`reasoning_effort`,
`temperature`, `top_p`, `tool_choice`, `max_tokens`, `max_completion_tokens`,
`thinking`, `output_config`, `response_format`, `parallel_tool_calls`,
`strict`, `store`, `stream_options`, `metadata`) plus `stop` from the
Databricks body allowlist (`providers.profiles.DATABRICKS_BODY_ALLOWLIST`).
Deliberately EXCLUDES that allowlist's `tools`/`messages`/`stream`/`model`:
`tools` already has its own never-silently-drop handling
(`providers.errors.is_tools_rejected_message` -- dropping it here would
silently break a tool-using session); `messages`/`stream`/`model` are core
wire shape, never an optional parameter a doctor probe would exercise.

Persisted in the SAME `<state_dir>/learned-rules.json` file, under the SAME
`"<provider>:<model>"` row every other learned fact in `providers.
learned_rules` already uses, in a `"params"` sub-object keyed by field name:
`{"<provider>:<model>": {"params": {"<field>": {"action": "drop"|"clamp",
"value": ..., "error": "<first 200 chars>", "date": "<ISO 8601>"}}}}` --
every existing key in that same row (`tools_rejected`, `reasoning_effort_
with_tools`, `ignored_params`, `mcp_fix`) is untouched by anything here.
"""

from __future__ import annotations

import difflib
import json
import os
import re
from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Optional

from halo_harness.providers.learned_rules import _LOCK, _key, _path, load_learned_rules

# 30 days: long enough a rule never re-pays the round trip against an
# endpoint that genuinely still rejects the field, short enough a since-
# fixed/transient rejection self-heals with no action needed -- same
# reasoning as `learned_rules.TOOLS_REJECTED_TTL_S`, just a longer window
# (a provider's accepted-parameter set changes far less often than a single
# flaky 400 does).
PARAM_RULE_TTL_DAYS = 30
PARAM_RULE_TTL_S = PARAM_RULE_TTL_DAYS * 24 * 60 * 60

WATCHED_PARAM_FIELDS = (
    "reasoning_effort", "temperature", "top_p", "tool_choice", "max_tokens",
    "max_completion_tokens", "thinking", "output_config", "response_format",
    "parallel_tool_calls", "strict", "store", "stream_options", "metadata",
    "stop",
)

# A field whose live value is nested one level down -- a "drop" removes the
# whole top-level key (same as every other field); a "clamp" replaces only
# the named sub-key, preserving any sibling the top-level dict also carries.
_NESTED_SUBFIELD = {"output_config": "effort"}

# The harness's own general effort vocabulary, widest end first is NOT the
# order -- lowest-to-highest, matching `providers.profiles.
# OPENAI_RESPONSES_EFFORT_LEVELS` exactly, so "nearest" clamps the same way
# `profiles.clamp_effort` already does (xhigh -> max when max is offered).
_EFFORT_ORDER = ("none", "minimal", "low", "medium", "high", "xhigh", "max")

_UNKNOWN_FIELD_RE = re.compile(r'unknown field\s*"([^"]+)"', re.IGNORECASE)
_QUOTED_RE = re.compile(r"'([^']+)'|\"([^\"]+)\"")

_DISPLAY_OVERRIDES = {"openrouter": "OpenRouter", "openai": "OpenAI", "huggingface": "Hugging Face",
                       "databricks": "Databricks", "anthropic": "Anthropic", "experiential": "Experiential Labs"}


def provider_display_name(provider: str) -> str:
    """Plain prose name for the transcript line -- a tiny, deliberately
    separate copy of `providers.errors._PROVIDER_DISPLAY_NAMES` (that name
    is module-private; this module stays decoupled from it rather than
    reaching across for a one-line table)."""
    return _DISPLAY_OVERRIDES.get(provider, provider.title())


@dataclass
class ParamFix:
    field: str
    action: str                 # "drop" | "clamp"
    value: object = None        # the clamped replacement; unset for "drop"
    error: str = ""             # first 200 chars of the upstream message


def describe_fix(fix: "ParamFix") -> str:
    """The clause the house-voice transcript line uses after "rejected
    <field> on this endpoint; " -- e.g. "dropped it" or "clamped it to
    'none'"."""
    return "dropped it" if fix.action == "drop" else f"clamped it to {fix.value!r}"


def _quoted_tokens(message: str) -> list:
    out = []
    for m in _QUOTED_RE.finditer(message or ""):
        tok = m.group(1) if m.group(1) is not None else m.group(2)
        if tok and tok not in out:
            out.append(tok)
    return out


def _looks_numeric(v) -> bool:
    try:
        float(v)
        return True
    except (TypeError, ValueError):
        return False


def _nearest_allowed(sent, allowed: list):
    """`sent` clamped to the closest member of `allowed`: exact match wins
    outright; an effort-vocabulary value (`_EFFORT_ORDER`) clamps the same
    way `profiles.clamp_effort` does (nearest by ordinal distance, ties
    broken toward the STRONGER allowed level, matching that function's own
    xhigh -> max convention); two numeric-looking strings compare as
    numbers; anything else falls back to the lexically closest allowed
    string, or simply the first allowed value when nothing is close."""
    if not allowed:
        return None
    if sent in allowed:
        return sent
    if sent in _EFFORT_ORDER and all(v in _EFFORT_ORDER for v in allowed):
        sent_idx = _EFFORT_ORDER.index(sent)
        ranked = sorted(allowed, key=lambda v: (abs(_EFFORT_ORDER.index(v) - sent_idx), -_EFFORT_ORDER.index(v)))
        return ranked[0]
    if _looks_numeric(sent):
        numeric = [(v, abs(float(v) - float(sent))) for v in allowed if _looks_numeric(v)]
        if numeric:
            return min(numeric, key=lambda t: t[1])[0]
    close = difflib.get_close_matches(str(sent), [str(v) for v in allowed], n=1)
    return close[0] if close else allowed[0]


def _field_mentions(message: str, body: dict) -> list:
    """Every `WATCHED_PARAM_FIELDS` entry that is BOTH a key this request
    actually sent (`body`) and literally named in `message`, earliest
    mention first (ties broken by `WATCHED_PARAM_FIELDS`' own order) -- so
    a message that happens to name a field this request never sent is
    never acted on, and the field the error is really about wins when more
    than one qualifies."""
    hits = []
    for field in WATCHED_PARAM_FIELDS:
        if field not in body:
            continue
        m = re.search(r"\b" + re.escape(field) + r"\b", message, re.IGNORECASE)
        if m:
            hits.append((m.start(), WATCHED_PARAM_FIELDS.index(field), field))
    hits.sort()
    return [f for _, _, f in hits]


def detect_param_rejection(status: int, message: str, body: Optional[dict] = None) -> Optional[ParamFix]:
    """The smallest fix for this (status, message) pair, or `None` when
    nothing in `WATCHED_PARAM_FIELDS` is both named in `message` and
    actually present in `body` (including a 400/422 that names no field at
    all -- normal error translation applies unchanged). `status` must be
    400 or 422, matching the brief's own "on any 400 or 422" rule."""
    if status not in (400, 422):
        return None
    message = message or ""
    body = body or {}

    unknown = _UNKNOWN_FIELD_RE.search(message)
    if unknown and unknown.group(1) in WATCHED_PARAM_FIELDS and unknown.group(1) in body:
        return ParamFix(field=unknown.group(1), action="drop", error=message[:200])

    fields = _field_mentions(message, body)
    if not fields:
        return None
    field = fields[0]
    sub = _NESTED_SUBFIELD.get(field)
    sent = body.get(field)
    if sub and isinstance(sent, dict):
        sent = sent.get(sub)
    allowed = [t for t in _quoted_tokens(message) if t != field]
    if allowed:
        return ParamFix(field=field, action="clamp", value=_nearest_allowed(sent, allowed), error=message[:200])
    return ParamFix(field=field, action="drop", error=message[:200])


def table_value_wins(field: str, profile) -> bool:
    """True when `profile` (a `providers.profiles.ProviderProfile`, or
    anything duck-typed the same way) carries its OWN explicit value for
    `field`, sourced from `model_table.json` -- "a model_table.json row
    still wins over a learned rule," the SAME precedence `resolve_profile`
    already applies to `reasoning_effort_with_tools`/`tools_rejected`.
    Only `temperature`/`top_p` are actually sourced from table rows onto a
    `ProviderProfile` today; every other watched field has no table-
    supplied value to defer to, so this is always False for them."""
    return field in ("temperature", "top_p") and getattr(profile, field, None) is not None


def apply_param_fix(body: dict, fix: "ParamFix") -> dict:
    """`body` with `fix` applied -- never mutates the input dict."""
    new_body = dict(body)
    sub = _NESTED_SUBFIELD.get(fix.field)
    if sub and isinstance(new_body.get(fix.field), dict):
        if fix.action == "clamp":
            new_body[fix.field] = {**new_body[fix.field], sub: fix.value}
        else:
            new_body.pop(fix.field, None)
        return new_body
    if fix.action == "clamp":
        new_body[fix.field] = fix.value
    else:
        new_body.pop(fix.field, None)
    return new_body


# ---------------------------------------------------------------------------
# Persistence: one more sub-object in the SAME per-endpoint row `providers.
# learned_rules` already reads/writes (`_key`/`_path`/`_LOCK`/`load_learned_
# rules` are that module's own shared low-level helpers, reused here rather
# than duplicated).
# ---------------------------------------------------------------------------

def _rule_age_s(date_str) -> float:
    """Seconds since `date_str` (an ISO 8601 string); `inf` for anything
    missing/unparseable so a malformed/ancient date always reads as stale
    rather than (worse) as freshly-learned."""
    if not isinstance(date_str, str):
        return float("inf")
    try:
        text = date_str[:-1] + "+00:00" if date_str.endswith("Z") else date_str
        dt = datetime.fromisoformat(text)
    except ValueError:
        return float("inf")
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=timezone.utc)
    return (datetime.now(timezone.utc) - dt).total_seconds()


def _write_rules(path, rules) -> None:
    """Best-effort, atomic write -- same tmp-file-then-replace shape every
    writer in `providers.learned_rules` already uses; never raises."""
    try:
        path.parent.mkdir(parents=True, exist_ok=True)
        tmp_path = path.with_name(path.name + f".tmp{os.getpid()}")
        tmp_path.write_text(json.dumps(rules, indent=2) + "\n", encoding="utf-8")
        os.replace(tmp_path, path)
    except OSError:
        pass


def _params_row(state_dir, provider: str, model: str) -> dict:
    row = load_learned_rules(state_dir).get(_key(provider, model))
    params = row.get("params") if isinstance(row, dict) else None
    return dict(params) if isinstance(params, dict) else {}


def learned_param_fix(state_dir, provider: str, model: str, field: str) -> Optional[dict]:
    """The learned fix for (provider, model, field), ONLY when it's fresh
    enough to apply PRE-EMPTIVELY (age <= `PARAM_RULE_TTL_S`) -- the shape
    a caller building a request consults BEFORE ever sending it, so an
    endpoint already proven to reject this field never pays for the same
    round trip twice. `None` when nothing is learned, or the learned rule
    has aged past the TTL -- the brief's "tried once without the fix
    before being reapplied": a stale rule is simply not pre-applied; if the
    SAME live rejection happens again, the ordinary reactive path relearns
    it (refreshing `date`, restarting the TTL); if it doesn't, the stale
    row is harmlessly left in place (still visible, and gets only staler,
    via `list_param_rules`)."""
    fix = _params_row(state_dir, provider, model).get(field)
    if not isinstance(fix, dict):
        return None
    return None if _rule_age_s(fix.get("date")) > PARAM_RULE_TTL_S else fix


def learn_param_fix(state_dir, provider: str, model: str, fix: "ParamFix") -> None:
    """Persist `fix` for (provider, model) -- ALWAYS refreshes `date` (this
    is only ever called after a LIVE retry with `fix` applied actually
    succeeded, never merely planned), restarting the 30-day TTL even when
    re-confirming an already-known rule. Best-effort, never raises."""
    with _LOCK:
        rules = load_learned_rules(state_dir)
        key = _key(provider, model)
        row = dict(rules.get(key)) if isinstance(rules.get(key), dict) else {}
        params = dict(row.get("params")) if isinstance(row.get("params"), dict) else {}
        params[fix.field] = {
            "action": fix.action, "value": fix.value, "error": fix.error,
            "date": datetime.now(timezone.utc).isoformat(timespec="seconds"),
        }
        row["params"] = params
        rules[key] = row
        _write_rules(_path(state_dir), rules)


def forget_param_fixes(state_dir, endpoint: str) -> bool:
    """`halo rules --forget <endpoint>`: clears every learned PARAM fix for
    `endpoint` (the exact `"<provider>:<model>"` key `list_param_rules`
    prints) -- leaves every OTHER learned field for that same endpoint
    (`tools_rejected`, `reasoning_effort_with_tools`, `ignored_params`,
    `mcp_fix`) untouched; those have their own forget surfaces (`halo mcp
    learned --forget`). `True` iff something was actually cleared."""
    with _LOCK:
        rules = load_learned_rules(state_dir)
        row = rules.get(endpoint)
        if not isinstance(row, dict) or not row.get("params"):
            return False
        row = dict(row)
        row.pop("params", None)
        if row:
            rules[endpoint] = row
        else:
            rules.pop(endpoint, None)
        _write_rules(_path(state_dir), rules)
        return True


def forget_all_param_rules(state_dir) -> int:
    """`halo models refresh --forget-rules`: clears every learned PARAM fix
    for EVERY endpoint (never the other learned fields) -- the blunt, whole-
    cache reset a catalog refresh reaches for after a provider-side change
    might have invalidated every rule at once. Returns how many endpoints
    actually had something cleared."""
    with _LOCK:
        rules = load_learned_rules(state_dir)
        cleared = 0
        for endpoint in list(rules):
            row = rules[endpoint]
            if not isinstance(row, dict) or not row.get("params"):
                continue
            cleared += 1
            row = dict(row)
            row.pop("params", None)
            if row:
                rules[endpoint] = row
            else:
                rules.pop(endpoint, None)
        if cleared:
            _write_rules(_path(state_dir), rules)
        return cleared


def list_param_rules(state_dir) -> list:
    """`halo rules`/`/rules`: one entry per learned (endpoint, field) PARAM
    fix, fresh and stale alike (age is exactly what lets a person DECIDE to
    forget a stale one) -- `[{"endpoint", "field", "action", "value",
    "age_s"}, ...]`, sorted by endpoint then field. Never raises; a
    missing/corrupt cache just lists nothing."""
    rules = load_learned_rules(state_dir)
    out = []
    for endpoint, row in rules.items():
        if not isinstance(row, dict):
            continue
        params = row.get("params")
        if not isinstance(params, dict):
            continue
        for field, fix in params.items():
            if isinstance(fix, dict):
                out.append({"endpoint": endpoint, "field": field, "action": fix.get("action"),
                            "value": fix.get("value"), "age_s": _rule_age_s(fix.get("date"))})
    out.sort(key=lambda r: (r["endpoint"], r["field"]))
    return out


# ---------------------------------------------------------------------------
# `halo doctor --probe-all --learn` (deliverable 2): pre-learns by sending
# one minimal request per OPTIONAL parameter to each configured Databricks
# endpoint -- opt-in, never run without the flag, cost estimated first.
# Excludes the effort family (reasoning_effort/thinking/output_config --
# `clamp_effort` already prevents most rejections pre-emptively, and the
# gpt-6/GLM/Claude live-400 paths cover the rest), `max_tokens` (always
# sent, not optional) and `tool_choice` (meaningless without `tools`, which
# this probe deliberately never sends -- a judge/decision-only endpoint
# must not see a stray tool catalog from a probe it never asked for).
# ---------------------------------------------------------------------------

# `providers.databricks.build_databricks_body` filters EVERY Databricks
# request down to `profiles.DATABRICKS_BODY_ALLOWLIST` before it ever
# reaches the wire -- probing a field outside that allowlist would probe
# nothing at all (it never leaves this process). PROBE_FIELDS is therefore
# the intersection: today that is temperature/top_p/stream_options/stop --
# this shrinks automatically if a later round widens that allowlist (the
# same reason `build_databricks_body`'s own docstring gives for reasoning_
# effort/stream_options having been added to it).
from halo_harness.providers.profiles import DATABRICKS_BODY_ALLOWLIST as _DBX_ALLOWLIST

PROBE_FIELDS = tuple(f for f in WATCHED_PARAM_FIELDS
                     if f not in ("reasoning_effort", "thinking", "output_config", "max_tokens", "tool_choice")
                     and f in _DBX_ALLOWLIST)

_PROBE_VALUES = {
    "temperature": 0.7, "top_p": 0.9, "max_completion_tokens": 16,
    "response_format": {"type": "text"}, "parallel_tool_calls": True, "strict": True,
    "store": False, "stream_options": {"include_usage": True},
    "metadata": {"halo_probe": "1"}, "stop": ["<|halo-probe|>"],
}


def estimate_probe_cost_line(endpoint_count: int, field_count: int = len(PROBE_FIELDS)) -> str:
    """The line `halo doctor --probe-all --learn` prints BEFORE sending
    anything -- the whole point of printing it first."""
    total = endpoint_count * field_count
    return (f"halo doctor --learn: this sends {total} minimal probe request(s) across {endpoint_count} "
            f"endpoint(s) ({field_count} optional parameter(s) each), each capped at 1 output token -- "
            f"a few cents at most.")


def probe_and_learn_params(state_dir, root: str, token: str, headers: dict, endpoint_names: list) -> list:
    """Sends one minimal chat request per `PROBE_FIELDS` entry to each of
    `endpoint_names` (a Databricks workspace root + token the caller
    already resolved, same shape `work_matrix.run_work_matrix` uses); a
    400/422 naming that field is planned and learned exactly like a live
    turn's own reactive path (`agent/loop.py`'s `_step`) would -- never
    retried here, there is no real turn to rescue, just a fact to record.
    Returns `[{"endpoint", "field", "learned": bool}, ...]`, one entry per
    probe actually sent; never raises -- a single endpoint's connect
    failure just skips that endpoint's remaining probes."""
    from halo_harness.providers.errors import upstream_error_text
    from halo_harness.providers.http import call_databricks_chat
    results = []
    for name in endpoint_names:
        for field in PROBE_FIELDS:
            body = {"messages": [{"role": "user", "content": "hi"}], "max_tokens": 1, field: _PROBE_VALUES[field]}
            try:
                result = call_databricks_chat(root, token, body, headers, state_dir, name)
            except Exception:
                continue
            learned = False
            try:
                if result.status in (400, 422):
                    if result.body_bytes is not None:
                        raw = result.body_bytes
                    else:
                        raw = result.resp.read() if result.resp else b""
                    try:
                        err_obj = json.loads(raw.decode("utf-8", "replace")) if raw else {}
                    except (json.JSONDecodeError, ValueError):
                        err_obj = {"error": {"message": raw.decode("utf-8", "replace")}}
                    fix = detect_param_rejection(result.status, upstream_error_text(err_obj), body)
                    if fix is not None:
                        learn_param_fix(state_dir, "databricks", name, fix)
                        learned = True
            finally:
                for closer in (result.resp, result.conn):
                    try:
                        if closer is not None:
                            closer.close()
                    except Exception:
                        pass
            results.append({"endpoint": name, "field": field, "learned": learned})
    return results
