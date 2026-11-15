"""halo_harness.crew.checks -- the checks on an agent's answer and on the models agents run on (Halo 3.6.0.0 R5b: moved
from agents_doctor.py, which went with bios).

    check_expectation(text, expect) -> bool       "non-empty" (real content), else a case-insensitive substring
    print_mode_argv(ref, prompt) -> argv          `halo -p <prompt> --model <ref> --max-turns 1`
    call_once(ref, prompt) -> str                 that command run once (smoke runs, probes); "" on any failure
    missing_model_provider(pref, catalogs=...)    the provider whose catalog does not know `pref`'s id
    check_dead_model_ids() / check_roles_hygiene() -> [line]   `halo doctor`'s rows on the model table (`roles.*`)
"""

from __future__ import annotations
from halo_harness.selfexec import python_argv  # 3.6.0.0 R10: never the working folder's copy

from typing import Optional


def check_expectation(response: str, expect: "Optional[str]") -> bool:
    if not expect:
        return True
    text = (response or "").strip()
    if expect.strip().lower() == "non-empty":
        return bool(text)
    return expect.lower() in text.lower()


def print_mode_argv(model_ref: str, prompt: str) -> "list[str]":
    """`halo -p <prompt> --model <ref> --max-turns 1` -- the one-shot
    print-mode command every smoke call, acceptance run and model probe
    (`model_probe.probe_model`) spawns."""
    import sys
    return [*python_argv(), "-p", prompt, "--model", model_ref, "--max-turns", "1"]




def call_once(model_ref: str, prompt: str, *, timeout: float = 60.0) -> str:
    """The REAL path -- `halo -p <prompt> --model <ref> --max-turns 1` as
    a subprocess, reusing the already-proven print-mode entry point
    rather than hand-building a second direct-provider-request pipeline
    just for this. Never raises; a launch/timeout failure degrades to
    empty output, which `check_expectation` already treats as a failure
    on its own (no separate error path needed here)."""
    from halo_harness import subprocess_safe as subprocess
    try:
        proc = subprocess.run(print_mode_argv(model_ref, prompt), capture_output=True, text=True, timeout=timeout)
        return (proc.stdout or "").strip()
    except Exception:
        return ""


def _model_family(ref: str) -> "str | None":
    """The rough model family of a ref -- the part after the route prefix,
    lowercased up to the first digit run (e.g. `or:z-ai/glm-5.3` ->
    `glm`, `ant:sonnet` -> `sonnet`, `ol:qwen3-coder:30b@lan` -> `qwen`,
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
            # role gets falsely flagged dead the moment the
            # configured Ollama host cannot be reached right now (verified:
            # `doctor --roles` on an all-local, otherwise-clean setup).
            return ids or None
    except Exception:
        return None
    return None


def missing_model_provider(pref, *, catalogs: dict, state_dir=None) -> "Optional[str]":
    """The provider prefix (`or`/`dbx`/`ol`) when `pref`'s id is not in that
    provider's catalog; None when it is, when the ref names no catalogued
    provider, or when the catalog cannot be read or is empty (never a false
    dead id). `catalogs` caches one read per provider across calls -- the
    one dead-id walk `check_dead_model_ids` and the run-start preflight
    share."""
    if not isinstance(pref, str) or ":" not in pref:
        return None
    provider = pref.split(":", 1)[0]
    if provider not in ("or", "dbx", "ol"):
        return None
    if provider not in catalogs:
        catalogs[provider] = _catalog_model_ids(provider, state_dir=state_dir)
    known = catalogs[provider]
    if not known:
        return None
    bare = pref.split(":", 1)[1].split("@")[0]
    return provider if bare not in known else None


def check_dead_model_ids(*, cwd=None, state_dir=None) -> "list[str]":
    """2.0.7: each `roles.*` model id the provider's own catalog does not know (it would 404 silently), with the fix.
    Providers without a readable catalog (or local lanes) are skipped, never guessed at."""
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
        provider = missing_model_provider(pref, catalogs=catalogs, state_dir=state_dir)
        if provider is not None:
            problems.append(
                f"{role}'s model id {pref!r} is not in the {provider} catalog -- requests for it 404 "
                f"silently (sub-agents come back empty). Pick a live id from the model picker, or "
                f"`halo models --refresh` first if the catalog is stale.")
    return problems


def check_roles_hygiene(*, cwd=None, state_dir=None) -> "list[str]":
    """The model table's (`roles.*`) warnings, one plain sentence each (2.0.6 round 7): no main model, a dead
    endpoint (the model's host unreachable), a judge in the coder's family. No model call; at most one reachability
    probe per gateway host."""
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
    # Only when NEITHER exists is there no main model.
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

    # 3. dead endpoints: one probe per distinct gateway host across the table
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
