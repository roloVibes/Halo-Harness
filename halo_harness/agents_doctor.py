"""halo_harness.agents_doctor -- Halo 2.0.4 round 4 (deliverable 6/8):
`halo doctor --agents` runs every agent bio's own `acceptance.prompt`
through a one-shot model call and checks the reply against `acceptance.
expect` ("non-empty" is a sentinel meaning "just needs real content",
anything else is a case-insensitive substring match) -- "running each
file's acceptance block against a mock in tests and the real model
live" (the brief's own wording: `call_fn` is the injectable mock seam,
omitted means the real `halo -p` subprocess path). ALSO validates the
active team template (refinement: "halo doctor --agents validates every
bio and the active template -- every referenced agent exists").
"""

from __future__ import annotations

from typing import Callable, Optional


def check_expectation(response: str, expect: "Optional[str]") -> bool:
    if not expect:
        return True
    text = (response or "").strip()
    if expect.strip().lower() == "non-empty":
        return bool(text)
    return expect.lower() in text.lower()


def _default_call(model_ref: str, prompt: str, *, timeout: float = 60.0) -> str:
    """The REAL path -- `halo -p <prompt> --model <ref> --max-turns 1` as
    a subprocess, reusing the already-proven print-mode entry point
    rather than hand-building a second direct-provider-request pipeline
    just for this. Never raises; a launch/timeout failure degrades to
    empty output, which `check_expectation` already treats as a failure
    on its own (no separate error path needed here)."""
    import subprocess
    import sys
    try:
        proc = subprocess.run(
            [sys.executable, "-m", "halo_harness", "-p", prompt, "--model", model_ref, "--max-turns", "1"],
            capture_output=True, text=True, timeout=timeout)
        return (proc.stdout or "").strip()
    except Exception:
        return ""


def run_acceptance(bio: dict, *, call_fn: "Optional[Callable[[str, str], str]]" = None,
                    default_model: "Optional[str]" = None) -> "tuple[bool, str]":
    """`(ok, message)` for ONE already-resolved bio. `(False, "no
    acceptance block")` when the bio defines none at all -- not
    necessarily a FAILURE of the bio itself, `run_all_acceptance`'s own
    caller decides how to count that."""
    acceptance = bio.get("acceptance") or {}
    prompt = acceptance.get("prompt")
    if not prompt:
        return False, "no acceptance block"
    models = bio.get("models") or {}
    model_ref = models.get("preference") or models.get("fallback") or default_model
    if not model_ref:
        return False, "no models.preference/fallback and no default model given -- nothing to call"
    caller = call_fn or _default_call
    try:
        response = caller(model_ref, prompt)
    except Exception as e:
        return False, f"call failed: {type(e).__name__}: {e}"
    ok = check_expectation(response, acceptance.get("expect"))
    snippet = (response or "")[:120].replace("\n", " ")
    return (ok, f"ok ({model_ref}): {snippet!r}") if ok else (ok, f"FAILED ({model_ref}): got {snippet!r}")


def run_all_acceptance(*, cwd=None, state_dir=None, call_fn=None,
                        names: "Optional[list]" = None) -> "list[tuple[str, bool, str]]":
    """`[(name, ok, message), ...]` for every agent bio `agents_yaml.
    list_agent_bios` finds (or just `names`, when given)."""
    from halo_harness.agents_yaml import list_agent_bios, resolve_agent_bio
    out: "list[tuple[str, bool, str]]" = []
    for name in (names if names is not None else list_agent_bios(cwd=cwd, state_dir=state_dir)):
        bio = resolve_agent_bio(name, cwd=cwd, state_dir=state_dir)
        if bio is None:
            out.append((name, False, "could not load/resolve this bio"))
            continue
        ok, message = run_acceptance(bio, call_fn=call_fn)
        out.append((name, ok, message))
    return out


def check_active_team(*, cwd=None, state_dir=None) -> "list[str]":
    """One plain sentence per problem with the ACTIVE team template
    (`team:` in config.json) -- `[]` when none is active, or the active
    one is fully valid. Every referenced agent bio must actually exist
    (`validate_team_template`'s own check)."""
    from halo_harness.theme import get_config_value
    active = get_config_value("team", default=None)
    if not active:
        return []
    from halo_harness.teams_yaml import load_team_template_raw, validate_team_template
    raw = load_team_template_raw(active, cwd=cwd, state_dir=state_dir)
    if raw is None:
        return [f"active team {active!r} could not be loaded"]
    problems = validate_team_template(raw, name=active, cwd=cwd, state_dir=state_dir)
    return [f"active team {active!r}: {p}" for p in problems]
