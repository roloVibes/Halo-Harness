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


def check_team_gates(name: "Optional[str]" = None, *, cwd=None, state_dir=None,
                     call_fn=None) -> "tuple[Optional[str], list[tuple[str, bool, str]]]":
    """Halo 2.0.5 round 5 (deliverable 4): `halo doctor --teams` -- resolve
    the named (or active) team template, then exercise its FIRST
    `required` gate end to end through `TeamControl.evaluate_stage`
    (the same gate the live agent loop runs between pipeline stages; the
    bio's own acceptance block is the checker, `call_fn` is the injectable
    model seam -- omitted means the real `halo -p` subprocess path, same as
    `run_acceptance`). `(team_name, [(stage, ok, message), ...])`;
    `(None, [...problem lines as (False,) tuples...])` when the team cannot
    even be resolved -- the CLI prints those as the problems they are."""
    from halo_harness.teams_runtime import load_team_control
    control = load_team_control(name, cwd=cwd, state_dir=state_dir)
    if control is None:
        return None, [("(team)", False, "no active team, or the named one could not be resolved")]
    results: "list[tuple[str, bool, str]]" = []
    required = [s for s in control.stages if s.get("gate") == "required"]
    if not required:
        results.append(("(pipeline)", False, "no required gate in this template -- nothing to exercise"))
        return control.name, results
    stage = required[0]
    bio = control.bio_for(stage.get("role"))
    acceptance = stage.get("acceptance") or (bio or {}).get("acceptance") or {}
    prompt = acceptance.get("prompt")
    if prompt and call_fn is None:
        # The live subprocess acceptance path -- the stage's own model.
        models = (bio or {}).get("models") or {}
        model_ref = models.get("preference") or models.get("fallback")
        if model_ref:
            try:
                response = _default_call(model_ref, prompt)
                ok = check_expectation(response, acceptance.get("expect"))
                results.append((stage.get("name"), ok,
                                f"gate exercise ({model_ref}): {'ok' if ok else 'FAILED'}"))
                return control.name, results
            except Exception as e:
                results.append((stage.get("name"), False, f"gate exercise call failed: {type(e).__name__}"))
                return control.name, results
    ok, note = control.evaluate_stage(stage, "", call_fn=call_fn)
    results.append((stage.get("name"), ok, f"gate exercise: {note}"))
    return control.name, results


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


# ---- 2.0.6 round 7: `halo doctor --roles` (roles hygiene, headless) --------

def _model_family(ref: str) -> "str | None":
    """The rough model family of a ref -- the part after the route prefix,
    lowercased up to the first digit run (e.g. `or:z-ai/glm-5.3` ->
    `glm`, `cc:sonnet` -> `sonnet`, `ol:qwen3-coder:30b@lan` -> `qwen`,
    `or:deepseek/deepseek-v4-pro` -> `deepseek`). Used ONLY for the
    self-preference-bias heuristic (judge in the same family as coder);
    a coarse bucket, never a claim about identity."""
    part = ref.split(":", 1)[1] if ":" in ref else ref
    part = part.split("@", 1)[0].split("/", 1)[-1]
    # the family is everything up to the first digit-run: "glm-5.3" ->
    # "glm", "qwen3-coder" -> "qwen", "deepseek-v4-pro" -> "deepseek",
    # "sonnet" -> "sonnet"
    fam = ""
    for ch in part.lower():
        if ch.isdigit():
            break
        if ch.isalnum() or ch == "-":
            fam += ch
        else:
            break
    fam = fam.rstrip("-")
    # a trailing "-v" is a version marker, not family ("deepseek-v4" ->
    # "deepseek", not "deepseek-v")
    if fam.endswith("-v"):
        fam = fam[:-2]
    return fam or None


def _catalog_model_ids(provider: str, *, state_dir=None) -> "set[str] | None":
    """The set of known model ids for one provider's catalog, or None when
    the catalog can't be read (never a false 'dead id' from a missing
    catalog). 2.0.7 dead-model-id round: `or:` reads models.json (the
    picker's own source, so a stale-but-known id stays quiet), `dbx:` the
    endpoints cache, `ol:` the host's live tag list (cheap, already the
    panel's own probe)."""
    try:
        if provider == "or":
            from halo_harness.providers.databricks import load_models_json
            from halo_harness.config.paths import bridge_home
            models = load_models_json(state_dir or bridge_home()) or {}
            # An EMPTY models.json means "never fetched / nothing cached" --
            # not "every id is dead". Read as unverifiable (None), never a
            # wall of false dead-id warnings on a fresh install.
            return set(models) or None
        if provider == "dbx":
            from halo_harness.providers.databricks import load_dbx_endpoints_json
            from halo_harness.config.paths import bridge_home
            endpoints = load_dbx_endpoints_json(state_dir or bridge_home()) or {}
            return set(endpoints)
        if provider == "ol":
            from halo_harness.providers.ollama import get_catalog, resolve_ollama_host
            host = resolve_ollama_host(None)
            if host is None:
                return None
            catalog = get_catalog(host)
            ids = {m.get("name") or m.get("model") for m in (catalog or {}).get("models", [])}
            # round-6-ci-red finding 6: an unreachable host (or one with no
            # cached catalog yet) makes `get_catalog` return `{"models":
            # []}`, same shape as a REAL empty catalog -- the SAME "never a
            # false dead-id from a missing catalog" rule the `or:` branch
            # above already applies must hold here too, or every `ol:`
            # role in the lineup gets falsely flagged dead the moment the
            # configured Ollama host cannot be reached right now (verified:
            # `doctor --roles` on an all-local, otherwise-clean lineup).
            return ids or None
    except Exception:
        return None
    return None


def check_dead_model_ids(*, cwd=None, state_dir=None) -> "list[str]":
    """2.0.7 dead-model-id detection (rolo's live 2.0.6 finding: the role
    table's `or:deepseek/deepseek-v4-pro-0813` was 404ing SILENTLY --
    sub-agents handed back empty results and nothing said why). Resolves
    every role's configured model against the provider's own catalog and
    reports each id the catalog does not know, naming the role and a
    concrete fix. Providers without a readable catalog (or local lanes,
    which have no catalog to check) are skipped, never guessed at."""
    from halo_harness.roles import configured_role_table
    problems: "list[str]" = []
    table = configured_role_table()

    def _pref_for(role):
        v = table.get(role)
        if isinstance(v, dict):
            return v.get("model")
        return v

    catalogs: "dict[str, set | None]" = {}
    for role in sorted(table):
        pref = _pref_for(role)
        if not isinstance(pref, str) or ":" not in pref:
            continue
        provider = pref.split(":", 1)[0]
        if provider not in ("or", "dbx", "ol"):
            continue
        if provider not in catalogs:
            catalogs[provider] = _catalog_model_ids(provider, state_dir=state_dir)
        known = catalogs[provider]
        if known is None:
            continue
        bare = pref.split(":", 1)[1].split("@")[0]
        if bare not in known:
            problems.append(
                f"{role}'s model id {pref!r} is not in the {provider} catalog -- requests for it 404 "
                f"silently (sub-agents come back empty). Pick a live id from the model picker, or "
                f"`halo models --refresh` first if the catalog is stale.")
    return problems


def check_roles_hygiene(*, cwd=None, state_dir=None) -> "list[str]":
    """The roles lineup's own warning set, run headless (2.0.6 round 7 /
    the v2.0.4 review's item 6): every warning the wizard's lineup editor
    shows inline, plus the two the editor does not -- a dead ENDPOINT (the
    configured model's host is unreachable) and judge-in-the-same-family-
    as-coder self-preference bias. One plain sentence per problem, `[]`
    when the lineup is clean.

    Sources: config.json's `roles` table (`configured_role_table`) and
    the bios' own `models.preference` for the roles the table leaves
    unset. No model calls, no MCP -- a fast local pass plus at most one
    reachability probe per distinct gateway host."""
    import re as _re
    from halo_harness.roles import configured_role_table
    from halo_harness.theme import get_config_value
    problems: "list[str]" = []
    table = configured_role_table()

    def _pref_for(role: str):
        v = table.get(role)
        if isinstance(v, dict):
            return v.get("model")
        return v

    # 1. a main model, from either spelling: an explicit roles.main, or
    # the top-level `model` key a bare config carries (the session's own
    # model -- exactly as valid; the VM's own config spells it that way).
    # Only when NEITHER exists is the lineup actually headless.
    top_model = get_config_value("model", default=None)
    if _pref_for("main") is None and not (isinstance(top_model, str) and top_model):
        problems.append("no main model -- neither roles.main nor the top-level `model` is set "
                        "(`halo setup roles` or the wizard's roles step fixes this).")
    # 2. judge in the same family as coder (self-preference bias)
    coder_pref, judge_pref = _pref_for("coder"), _pref_for("judge")
    if coder_pref and judge_pref:
        cf, jf = _model_family(coder_pref), _model_family(judge_pref)
        if cf and jf and cf == jf:
            problems.append(f"judge and coder are both {cf!r}-family models ({judge_pref} / {coder_pref}) "
                            " -- a judge from the same family shares its biases; pick a different "
                            "family for one of them.")

    # 3. bios referenced by the table must exist and have a model
    from halo_harness.agents_yaml import list_agent_bios, resolve_agent_bio
    known_bios = set(list_agent_bios(cwd=cwd, state_dir=state_dir))

    # 4. dead endpoints: one probe per distinct gateway host across the table
    hosts: "dict[str, list[str]]" = {}
    for role, v in table.items():
        pref = _pref_for(role)
        if not isinstance(pref, str) or not pref:
            continue
        route = pref.split(":", 1)[0] if ":" in pref else ""
        # 2.0.6 review finding 1 (MAJOR, fixed): the dbx: probe used the
        # literal string "databricks" as a hostname -- never resolvable, a
        # false "unreachable" warning on every run. The REAL workspace
        # host comes from the same chain init_cli uses (env -> settings),
        # stripped to its bare hostname; with none configured the dbx:
        # roles are reported as "host not configured" instead of probing
        # a name that can never answer.
        if route in ("or", "xp", "hf"):
            host = {"or": "openrouter.ai", "xp": "experiential",
                    "hf": "huggingface.co"}[route]
            hosts.setdefault(host, []).append(f"{role}={pref}")
        elif route == "dbx":
            from halo_harness.init_cli import _known_databricks_host
            from urllib.parse import urlparse as _urlparse
            dbx_host = _known_databricks_host()
            bare = None
            if dbx_host:
                bare = _urlparse(dbx_host if "//" in dbx_host else f"https://{dbx_host}").hostname
            if bare:
                hosts.setdefault(bare, []).append(f"{role}={pref}")
            else:
                problems.append(f"dbx: roles configured ({pref}) but no DATABRICKS_HOST is set -- "
                                "the gateway cannot be probed (run `halo init --preset work`).")
    from halo_harness.providers.http import open_upstream
    for host, uses in hosts.items():
        try:
            conn = open_upstream(host, 443, True, connect_timeout=4.0)
            conn.close()
        except Exception:
            problems.append(f"gateway {host} is unreachable right now -- {', '.join(uses[:3])}"
                            + (f" (+{len(uses) - 3} more)" if len(uses) > 3 else "")
                            + "; the roles using it will fail until it is back.")
    return problems
