"""halo_harness.subscription_scrub -- no agent bio and no lineup ever runs on
a subscription route (Halo 3.0.2.0).

The owner's rule: "scrub all the agent bios and templates that use
subscriptions as their models; all of that should be removed and not
enabled on any pre-made bios or templates, plus it shouldn't occur
regardless so people don't get banned." Three layers:

1. The shipped templates name no `cc:`/`cx:` model (pinned by
   tests/test_subscription_defaults.py).
2. Copies already on disk are rewritten: `scrub_files` walks the user and
   project `agents/` and `teams/` folders and swaps every `cc:`/`cx:` ref
   for its OpenRouter equivalent (`equivalent_ref`), keeping the file
   otherwise byte-for-byte. It runs once per process whenever lineups are
   listed or resolved, and by hand as `halo subscriptions scrub`.
3. The resolvers never carry one: `resolve_agent_bio` and
   `resolve_role_table` map a `cc:`/`cx:` ref the same way at resolve time
   (a bio someone hand-wrote after the scrub), whether or not the routes
   are accepted. Acceptance still governs the SESSION model (`/model
   cc:...`); it never reaches a bio or a lineup.
"""

from __future__ import annotations

import re
from pathlib import Path
from typing import Optional

SUB_PREFIXES = ("cc:", "cx:")
_SUB_REF_RE = re.compile(r"\b(cc|cx):([A-Za-z0-9][\w.\-]*)")
_CLAUDE_ID_RE = re.compile(r"^claude-([a-z]+)-(\d+)(?:-(\d+))?(?:-\d{8})?$")
_FAMILY_LATEST = {"opus": "anthropic/claude-opus-5.5", "sonnet": "anthropic/claude-sonnet-5.5",
                  "haiku": "anthropic/claude-haiku-5.5", "fable": "anthropic/claude-fable-5.1"}
MODEL_KEYS = ("preference", "fallback", "escalation")


def _claude_to_openrouter(name: str) -> Optional[str]:
    """`claude-opus-5-5` -> `anthropic/claude-opus-5.5`; a bare family name
    (`opus`, `sonnet`) -> that family's current OpenRouter row."""
    try:
        from halo_harness.providers.cc_models import CC_ALIASES
        name = CC_ALIASES.get(name, name)
    except Exception:
        pass
    if name in _FAMILY_LATEST:
        return _FAMILY_LATEST[name]
    m = _CLAUDE_ID_RE.match(name)
    if not m:
        return None
    family, major, minor = m.group(1), m.group(2), m.group(3)
    return f"anthropic/claude-{family}-{major}" + (f".{minor}" if minor else "")


def _codex_to_openrouter(name: str) -> Optional[str]:
    try:
        from halo_harness.providers.codex_models import CODEX_ALIASES
        name = CODEX_ALIASES.get(name, name)
    except Exception:
        pass
    return f"openai/{name}" if re.match(r"^[\w.\-]+$", name) else None


def equivalent_ref(ref) -> Optional[str]:
    """The OpenRouter ref a subscription ref stands for (`or:...`); a ref
    that is not a subscription route comes back unchanged; None when no
    equivalent is known (the caller falls through to the default model)."""
    if not isinstance(ref, str) or not ref.startswith(SUB_PREFIXES):
        return ref
    route, _, name = ref.partition(":")
    mapped = _claude_to_openrouter(name) if route == "cc" else _codex_to_openrouter(name)
    return f"or:{mapped}" if mapped else None


def scrub_model_block(models: dict, *, where: str = "") -> list:
    """Rewrite preference/fallback/escalation in place; the notes say what moved."""
    notes = []
    if not isinstance(models, dict):
        return notes
    for key in MODEL_KEYS:
        ref = models.get(key)
        if isinstance(ref, str) and ref.startswith(SUB_PREFIXES):
            new = equivalent_ref(ref)
            if new:
                models[key] = new
                notes.append(f"{where or 'models'}.{key}: {ref} -> {new} (subscription routes never run a bio)")
            else:
                models.pop(key, None)
                notes.append(f"{where or 'models'}.{key}: {ref} dropped (no API equivalent known; falls through)")
    return notes


def scrub_text(text: str) -> "tuple[str, list]":
    """Every `cc:`/`cx:` token in a YAML file swapped for its equivalent;
    one that has none is left for the resolver to drop."""
    changes = []

    def swap(m):
        ref = m.group(0)
        new = equivalent_ref(ref)
        if new and new != ref:
            changes.append(f"{ref} -> {new}")
            return new
        return ref
    return _SUB_REF_RE.sub(swap, text), changes


def _dirs(state_dir, cwd) -> list:
    out = []
    try:
        from halo_harness.agents_yaml import user_agents_dir
        from halo_harness.teams_yaml import user_teams_dir
        out += [user_agents_dir(state_dir=state_dir), user_teams_dir(state_dir=state_dir)]
    except Exception:
        pass
    if cwd:
        out += [Path(cwd) / ".halo" / "agents", Path(cwd) / ".halo" / "teams"]
    return [Path(d) for d in out if d]


def scrub_files(*, state_dir=None, cwd=None) -> list:
    """Rewrite every bio and lineup under the user and project folders;
    returns [(path, [changes])] for the files that changed. Shipped
    templates are never touched (they are clean, and read-only)."""
    done = []
    for d in _dirs(state_dir, cwd):
        if not d.is_dir():
            continue
        for path in sorted(d.glob("*.yaml")):
            try:
                text = path.read_text(encoding="utf-8")
            except OSError:
                continue
            new, changes = scrub_text(text)
            if changes and new != text:
                try:
                    path.write_text(new, encoding="utf-8", newline="")
                    done.append((path, changes))
                except OSError:
                    continue
    return done


_SCRUBBED: set = set()


def scrub_once(*, state_dir=None, cwd=None) -> list:
    """`scrub_files` once per process per (state_dir, cwd) -- the hook the
    lineup listing and the resolvers call."""
    key = (str(state_dir or ""), str(cwd or ""))
    if key in _SCRUBBED:
        return []
    _SCRUBBED.add(key)
    try:
        return scrub_files(state_dir=state_dir, cwd=cwd)
    except Exception:
        return []
