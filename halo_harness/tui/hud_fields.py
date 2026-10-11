"""halo_harness.tui.hud_fields -- the slot vocabulary: turns the StatusBar's
live state plus the strings `_refresh_display` already formatted into the
`{slot: HudField}` dict every HUD skin draws from (Halo 2.0.8).

Every field Halo's status bar shows is reachable through a slot, so a skin
only chooses WHERE each one goes; it never recomputes a value.
"""

from __future__ import annotations

from rich.text import Text

from halo_harness.model_display import format_live_token_count, truncate_label_left
from halo_harness.tui.hud import HudField

_PROVIDER_SHORT = {
    "openrouter": "or", "databricks": "dbx", "ollama": "ol", "experiential": "xp", "anthropic": "api",
    "huggingface": "hf", "typesafe": "ts", "codex": "cx", "claude": "cc",
}


def _provider_chips(bar) -> list:
    names = []
    prefix = bar.model.split(":", 1)[0] if bar.model and ":" in bar.model else ""
    if prefix:
        try:
            from halo_harness.providers.enablement import canonical
            names.append(canonical(prefix))
        except Exception:
            names.append(prefix)
    for name in bar.balance_segments:
        if name not in names:
            names.append(name)
    return [_PROVIDER_SHORT.get(n, str(n)[:4]) for n in names][:3]


def _pct_tone(used_pct) -> str:
    if used_pct is None:
        return "dim"
    return "bad" if used_pct >= 90 else ("warn" if used_pct >= 70 else "ok")


def build_fields(bar, s: dict) -> dict:
    """`bar` is the StatusBar; `s` the strings its `_refresh_display` built
    (cost_str, ctx_str, or_balance_str, ... plus `cwd_short`)."""
    f: dict = {}
    used_pct = bar.context_pct
    f["model"] = HudField(bar.model, truncate_label_left(bar.model, 14))
    if bar.context_limit:
        remaining = max(0, bar.context_limit - bar.context_tokens)
        rem = format_live_token_count(remaining)
        f["tokens"] = HudField(f"{rem} left", rem, _pct_tone(used_pct))
        rem_pct = max(0.0, 100.0 - (used_pct or 0.0))
        f["context"] = HudField(f"{rem_pct:.0f}%", f"{rem_pct:.0f}%", _pct_tone(used_pct), rem_pct / 100.0)
    else:
        f["tokens"] = HudField(f"{format_live_token_count(bar.context_tokens)} used", "", "dim")
        f["context"] = HudField("--%", "", "dim")
    mcp_tone = "ok" if (bar.mcp_total and bar.mcp_connected == bar.mcp_total) else "warn"
    f["mcp"] = HudField(s["mcp_str"], f"{bar.mcp_connected}/{bar.mcp_total}", mcp_tone)
    if bar.tools_loaded is not None:
        f["tools"] = HudField(f"{bar.tools_loaded} tools", str(bar.tools_loaded), mcp_tone)
    else:
        f["tools"] = f["mcp"]
    cost = s["cost_str"]
    balance = s["or_balance_str"]
    f["cost"] = HudField(f"{cost} · {balance}" if balance else cost, cost.split(" · ")[0], "")
    chips = _provider_chips(bar)
    f["providers"] = HudField(" ".join(chips) if chips else "-", chips[0] if chips else "-", "ok" if chips else "dim")
    if bar.cwd:
        f["cwd"] = HudField(s["loc_str"], s["cwd_short"], "dim")
    if bar.branch:
        f["branch"] = HudField(bar.branch, "", "dim")
    if s.get("area_str"):  # the cwd's last component, the branch as its sub-label
        f["area"] = HudField(f"{s['area_str']} · {bar.branch}" if bar.branch else s["area_str"], s["area_str"], "dim")
    f["turns"] = HudField(f"{bar.turn_count:02d}", "", "dim" if not bar.turn_count else "")
    f["mode"] = HudField(s["mode_str"], s["mode_str"])
    for slot, key, tone in (("effort", "effort_str", ""), ("needs_you", "needs_you_str", "warn"),
                            ("agents", "agents_str", ""), ("offline", "offline_str", "warn"),
                            ("gov", "gov_str", "warn"), ("new", "new_str", ""), ("hang", "hang_str", "warn"),
                            ("throughput", "throughput_str", "dim")):
        if s.get(key):
            f[slot] = HudField(s[key], "", tone)
    if s["permission_str"]:
        f["permission"] = HudField(s["permission_str"], "permission needed", "warn")
    bg = s["bg_jobs_str"]
    if bg:
        f["bg"] = HudField(f"{bg} · {s['oldest_str']}" if s["oldest_str"] else bg, bg, "")
    if s["spinner_str"]:
        word = s["spinner_str"].split(" · ")[0]
        f["phase"] = HudField(s["spinner_str"], word, "warn")
        if s.get("elapsed_str"):
            f["elapsed"] = HudField(s["elapsed_str"], "", "warn")
    if bar.statusline_text:
        try:
            plain = Text.from_ansi(bar.statusline_text).plain
        except Exception:
            plain = bar.statusline_text
        f["statusline"] = HudField(plain, "", "dim")
    return f
