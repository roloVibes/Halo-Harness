"""halo_harness.providers.dialect -- Halo 3.3.6.0 R4: the dialect record, how
Halo talks to one model on one host (plans/local-model-fit-brief.md Part G1;
Part E gates where a model goes, this is how Halo addresses it).

    record(host, model, *, state_dir) -> {instruction_placement: system | user-turn, strip_fences: bool,
        reply_reserve: int, json_repair: {on, attempts}, stop_quirks: [str], loop_guard: {on, window},
        thinking: native | off | strip, tools_max: int | None, from: {field: battery | ledger | user | default}}
    set_fields(host, model, {field: value}, by="user") / reset(host, model, field=None)
    (providers/dialect_refine.py: refine(host, model, *, state_dir) -> [lines], the ledger's rules)
    view(record) -> {fields: [{field, value, from, title, help}], lines: [...]}   the card's block
    parse(field, text) -> value                   `halo models dialect --set field=value`

Filled from the battery's profile: a weak system role -> user-turn; a fenced JSON
reply -> strip fences; a thinking model -> native thinking and a reserve of at
least 300; the reply reserve from the probes' longest answer; a stop token seen in
a reply (`<|im_end|>`, `<|eot_id|>`, ...) -> a stop quirk; no tool calling ->
tools_max 0. A JSON failure in the probe -> two repair attempts. Refined from the
ledger (the model's newest 20 calls on the host): a reply cut in over 10 % of them
raises the reserve one step; a loop the guard saw turns the guard on.

Stored at `ollama.profiles["<host>|<model>"]["dialect"]` (ollama_steward/profiles.py):
only the fields that differ from what the battery says, each with its `from`. A
change Halo makes goes through the steward's apply modes (auto: written; review: a
proposal in the steward's journal; off: none). A user's edit always wins and is
marked `user`; the ledger never overwrites it.
"""

from __future__ import annotations

from typing import Optional

FIELDS = ("instruction_placement", "strip_fences", "reply_reserve", "json_repair", "stop_quirks", "loop_guard",
          "thinking", "tools_max")
TITLES = {"instruction_placement": "Instructions go in", "strip_fences": "Strip ``` fences before parsing",
          "reply_reserve": "Reply reserve (tokens)", "json_repair": "JSON repair loop", "stop_quirks": "Stop tokens",
          "loop_guard": "Loop guard", "thinking": "Thinking", "tools_max": "Tools offered at most"}
HELP = {"instruction_placement": "system: Halo's instructions in the system message; user-turn: at the front of the "
                                 "first user message (a model that ignores the system role)",
        "strip_fences": "a JSON reply wrapped in a ``` fence is unwrapped before it is parsed",
        "reply_reserve": "the least room the reply gets (num_predict); a reply cut at the window's end raises it",
        "json_repair": "a reply that does not parse is asked again with the parse error, at most this many times",
        "stop_quirks": "extra stop strings sent with every call (a model that prints its end token)",
        "loop_guard": "the same span of this many tokens three times stops the reply",
        "thinking": "native: read its thinking as thinking; off: ask for none; strip: cut <think> text out of the reply",
        "tools_max": "how many tools the model is offered (0: none; empty: the window decides)"}
STEPS = (256, 512, 1024, 2048, 4096, 8192, 16384, 32768)
STOP_TOKENS = ("<|im_end|>", "<|eot_id|>", "<|end|>", "<|endoftext|>", "</s>", "<end_of_turn>")


def defaults() -> dict:
    return {"instruction_placement": "system", "strip_fences": True, "reply_reserve": 1024,
            "json_repair": {"on": True, "attempts": 1}, "stop_quirks": [], "loop_guard": {"on": False, "window": 40},
            "thinking": "native", "tools_max": None}


def _reply_reserve(p: dict) -> int:
    longest = max([int((e or {}).get("eval_count") or 0) for e in (p.get("evidence") or {}).values()
                   if isinstance(e, dict)] or [0])
    want = max(256, longest * 2, 300 if p.get("reasoning") == "thinking" else 0)
    return next((s for s in STEPS if s >= want), STEPS[-1])


def from_profile(p: Optional[dict]) -> "tuple[dict, dict]":
    """(values, from) the battery's profile says; the rest are the defaults."""
    vals, src = defaults(), {f: "default" for f in FIELDS}
    if not p:
        return vals, src
    vals["instruction_placement"] = "user-turn" if p.get("system_role") == "weak" else "system"
    vals["strip_fences"] = True
    vals["thinking"] = "native"
    vals["reply_reserve"] = _reply_reserve(p)
    vals["json_repair"] = {"on": True, "attempts": 2 if p.get("output") == "prose" else 1}
    texts = " ".join(str((e or {}).get("content") or "") for e in (p.get("evidence") or {}).values() if isinstance(e, dict))
    vals["stop_quirks"] = [t for t in STOP_TOKENS if t in texts]
    if p.get("tools") == "no":
        vals["tools_max"] = 0
    for f in ("instruction_placement", "strip_fences", "reply_reserve", "json_repair", "thinking"):
        src[f] = "battery"
    if vals["stop_quirks"]:
        src["stop_quirks"] = "battery"
    if p.get("tools") == "no":
        src["tools_max"] = "battery"
    return vals, src


def _ok(field: str, v) -> bool:
    if field == "instruction_placement":
        return v in ("system", "user-turn")
    if field == "thinking":
        return v in ("native", "off", "strip")
    if field == "strip_fences":
        return isinstance(v, bool)
    if field == "reply_reserve":
        return isinstance(v, int) and not isinstance(v, bool) and 1 <= v <= 131072
    if field == "tools_max":
        return v is None or (isinstance(v, int) and not isinstance(v, bool) and 0 <= v <= 512)
    if field == "stop_quirks":
        return isinstance(v, list) and all(isinstance(x, str) and x for x in v) and len(v) <= 8
    if field == "json_repair":
        return isinstance(v, dict) and isinstance(v.get("on"), bool) and isinstance(v.get("attempts"), int) \
            and 0 <= v["attempts"] <= 3
    if field == "loop_guard":
        return isinstance(v, dict) and isinstance(v.get("on"), bool) and isinstance(v.get("window"), int) \
            and 8 <= v["window"] <= 400
    return False


def clean_stored(d: dict) -> dict:
    """Only known fields of the right shape, and their `from` (user | ledger)."""
    if not isinstance(d, dict):
        return {}
    out = {f: d[f] for f in FIELDS if f in d and _ok(f, d[f])}
    frm = d.get("from") if isinstance(d.get("from"), dict) else {}
    if out:
        out["from"] = {f: (frm.get(f) if frm.get(f) in ("user", "ledger", "hub") else "user") for f in out}
    return out


def _key(host, model) -> str:
    from halo_harness.ollama_steward.profiles import key_for
    return key_for(getattr(host, "name", host), model)


def stored(host, model) -> dict:
    from halo_harness.ollama_steward.profiles import all_profiles
    return dict((all_profiles().get(_key(host, model)) or {}).get("dialect") or {})


def record(host, model: str, *, state_dir=None, profile=None) -> dict:
    """The record in force: the battery's facts, then what is stored (the ledger's refinements, your edits)."""
    if profile is None and state_dir is not None:
        from halo_harness.providers.ollama_capability import profile_for
        profile = profile_for(state_dir, model, getattr(host, "name", host))
    vals, src = from_profile(profile)
    mine = clean_stored(stored(host, model))
    for f in FIELDS:
        if f in mine:
            vals[f], src[f] = mine[f], mine["from"][f]
    return {**vals, "from": src, "model": model, "host": getattr(host, "name", host)}


def _write(host, model: str, d: dict, note: str) -> dict:
    from halo_harness.ollama_steward.profiles import all_profiles, set_field
    key = _key(host, model)
    by = (all_profiles().get(key) or {}).get("by") or "steward"
    return set_field(key, "dialect", clean_stored(d) or None, by=by, note=note[:300])


def set_fields(host, model: str, changes: dict, *, by: str = "user") -> "tuple[dict, list]":
    """(the stored dialect, problems): each field checked; `by` user always wins, ledger never over a user field."""
    d, bad = stored(host, model), []
    frm = dict(d.get("from") or {})
    for f, v in (changes or {}).items():
        if f not in FIELDS or not _ok(f, v):
            bad.append(f"{f}: {HELP.get(f, 'not a dialect field')}")
            continue
        if by != "user" and frm.get(f) == "user":
            continue
        d[f], frm[f] = v, by
    d["from"] = frm
    if not bad:
        _write(host, model, d, f"dialect: {', '.join(changes)} set by {by}")
    return clean_stored(d), bad


def reset(host, model: str, field: Optional[str] = None) -> dict:
    d = stored(host, model)
    if field:
        d.pop(field, None)
        (d.get("from") or {}).pop(field, None)
    else:
        d = {}
    _write(host, model, d, f"dialect: {field or 'every field'} back to what the battery says")
    return clean_stored(d)


def parse(field: str, text: str):
    t = str(text).strip()
    if field in ("strip_fences",):
        return t.lower() in ("1", "true", "on", "yes")
    if field in ("reply_reserve",):
        return int(t)
    if field == "tools_max":
        return None if t.lower() in ("", "none", "auto") else int(t)
    if field == "stop_quirks":
        return [x for x in (s.strip() for s in t.split(",")) if x]
    if field in ("json_repair", "loop_guard"):
        on, _, n = t.partition(":")
        off = on.lower() in ("off", "false", "0", "no")
        num = int(n) if n.strip() else (1 if field == "json_repair" else 40)
        return {"on": not off, "attempts": num} if field == "json_repair" else {"on": not off, "window": num}
    return t


def value_word(field: str, v) -> str:
    if isinstance(v, dict):
        return ("on" if v.get("on") else "off") + (f", {v['attempts']} attempt{'s' if v['attempts'] != 1 else ''}"
                                                   if "attempts" in v else f", {v.get('window')} tokens")
    if isinstance(v, bool):
        return "yes" if v else "no"
    if isinstance(v, list):
        return ", ".join(v) or "none"
    if v is None:
        return "the window decides"
    return f"{v:,}" if isinstance(v, int) else str(v)


def view(rec: dict) -> dict:
    frm = rec.get("from") or {}
    fields = [{"field": f, "value": rec.get(f), "from": frm.get(f, "default"), "title": TITLES[f], "help": HELP[f],
               "word": value_word(f, rec.get(f))} for f in FIELDS]
    return {"fields": fields, "lines": [f"{x['title'].lower()}: {x['word']} ({x['from']})" for x in fields]}
