"""halo_harness.mcp.doctor_deep -- Halo 2.0.4 round 6 ("MCP connectivity
deep dive"): the orchestrator over `mcp.doctor_probe`'s evidence -- the
model's ONE-fix proposal, applying it only on a yes, the learned-rules
replay, and the per-server "last diagnosis" record `/mcp` and `halo doctor
--mcp deep` both read. No safety/refusal language: a proposal is described
and applied on a yes, never gated by any other judgement.
"""

from __future__ import annotations

import json
import os
import re
import time
from dataclasses import dataclass
from pathlib import Path
from typing import Callable, Optional

# ---- the model's one-line fix proposal --------------------------------------

_FIX_PREFIXES = {
    "CONFIG_EDIT": "config_edit", "INSTALL": "install", "PATH": "path",
    "URL": "url", "ENV": "env",
}
# Only these three are things the harness can mechanically DO to a config
# file itself (write a key/value, swap the command path, swap the url) --
# "missing package"/"env var to set" are always advisory: the exact
# command/var name is SHOWN for the user to act on, same as `mcp_cli.
# install_hint`'s own existing "the line is for the user to run" contract.
_MECHANICAL_KINDS = frozenset({"config_edit", "path", "url"})

FIX_SYSTEM_PROMPT = (
    "You are diagnosing one failing MCP server for Halo's `doctor --mcp deep`. You are given the "
    "probe evidence (every step tried, in order, with what happened) and the server's resolved "
    "config entry. Reply with EXACTLY ONE line naming ONE concrete fix, in ONE of these forms "
    "(pick whichever matches the real problem; no other text, no explanation):\n"
    "CONFIG_EDIT: <key>=<value>   (a key already in the entry, or env.<NAME>=<value> for one env var)\n"
    "INSTALL: <the exact shell command to install the missing dependency>\n"
    "PATH: <the exact correct path to the command>\n"
    "URL: <the exact corrected url, including the port if that's what changed>\n"
    "ENV: <the NAME ONLY of an environment variable the user needs to set -- never a value>\n"
    "If nothing in the evidence points at a fixable cause, reply with exactly: ENV: UNKNOWN"
)


@dataclass
class FixProposal:
    kind: str       # config_edit | install | path | url | env | other
    detail: str
    raw_text: str

    @property
    def mechanically_appliable(self) -> bool:
        return self.kind in _MECHANICAL_KINDS

    def to_dict(self) -> dict:
        return {"kind": self.kind, "detail": self.detail, "raw_text": self.raw_text}

    @staticmethod
    def from_dict(d: dict) -> "Optional[FixProposal]":
        if not isinstance(d, dict) or not d.get("kind"):
            return None
        return FixProposal(kind=d["kind"], detail=d.get("detail", ""), raw_text=d.get("raw_text", ""))


def parse_fix_proposal(reply: Optional[str]) -> Optional[FixProposal]:
    """The model's reply -> one `FixProposal` -- `None` only for a blank/
    empty reply (a call that returned nothing at all). Anything else
    always yields A proposal: a recognized `TAG: detail` line classifies
    into one of the five kinds; anything else is kept verbatim as kind
    "other" (shown to the user, never silently dropped, never mechanically
    applied)."""
    if not reply or not reply.strip():
        return None
    first_line = reply.strip().splitlines()[0].strip()
    m = re.match(r"^([A-Za-z_]+)\s*:\s*(.+)$", first_line)
    if m and m.group(1).upper() in _FIX_PREFIXES:
        kind = _FIX_PREFIXES[m.group(1).upper()]
        detail = m.group(2).strip()
        return FixProposal(kind=kind, detail=detail, raw_text=f"{m.group(1).upper()}: {detail}")
    return FixProposal(kind="other", detail=first_line, raw_text=first_line)


# ---- failure signature (for the learned-rules replay) -----------------------

def _normalize_fingerprint_text(text: str) -> str:
    """The first non-blank line of `text`, lowercased, with every run of
    digits collapsed to `#` -- stable across repeats of the SAME
    underlying failure even when a pid/port/timestamp in the raw message
    differs run to run."""
    first_line = next((ln.strip() for ln in (text or "").splitlines() if ln.strip()), "")
    return re.sub(r"\d+", "#", first_line.lower())


def failure_signature(*, command: Optional[str], error_text: str) -> str:
    """"command basename + error class + stderr fingerprint" (brief
    deliverable 3, verbatim) -- `providers.learned_rules.learn_mcp_fix`'s
    own key. Deterministic and side-effect-free; never raises."""
    import hashlib
    base = re.split(r"[\\/]", (command or "").strip())[-1].lower() or "?"
    for suffix in (".exe", ".cmd", ".bat", ".ps1"):
        if base.endswith(suffix):
            base = base[: -len(suffix)]
            break
    m = re.match(r"^([A-Za-z_][A-Za-z0-9_]*)", (error_text or "").strip())
    error_class = m.group(1) if m else "Unknown"
    normalized = _normalize_fingerprint_text(error_text)
    fp = hashlib.sha256(normalized.encode("utf-8", "replace")).hexdigest()[:12]
    return f"{base}:{error_class}:{fp}"


# ---- config entry for the model prompt (masked) -----------------------------

def config_entry_for_prompt(cfg) -> dict:
    """A JSON-shaped, SECRET-MASKED view of `cfg` for the model prompt --
    every credential-shaped env/header value is blanked the same way
    `manager.expand_string(credential_blank=True)` already blanks one in a
    url/header, applied here to the full entry rather than one string."""
    from halo_harness.mcp.manager import _looks_like_credential
    env = {k: ("***" if _looks_like_credential(k) else v) for k, v in (cfg.env or {}).items()}
    headers = {k: "***" for k in (cfg.headers or {})}
    out = {"type": cfg.type, "scope": cfg.scope}
    if cfg.type == "stdio":
        out["command"] = cfg.command
        out["args"] = list(cfg.args or [])
        out["env"] = env
        if cfg.cwd:
            out["cwd"] = cfg.cwd
    else:
        from halo_harness.mcp.doctor_probe import mask_url
        out["url"] = mask_url(cfg.url)
        if headers:
            out["headers"] = headers
    if cfg.timeout_ms:
        out["timeout"] = cfg.timeout_ms
    return out


# ---- the model call ----------------------------------------------------------

def _default_model_call(cwd: Path) -> "Callable[[str, str], str]":
    """A real one-shot call to "the session model (or the judge role when
    one is configured)" -- the SAME throwaway-session + role-resolution
    plumbing `halo improve`'s own drafting call already established
    (`headless.build_session(bare=True)` + `Session.call_small_model`),
    never a second model-calling pipeline. `roles.resolve_role_ref("judge",
    ...)` already returns the session's own model/profile UNCHANGED when
    no judge role is configured (its own "nothing resolved -> reuse parent
    objects" contract) -- exactly "the session model, or the judge role
    when one is configured", with no extra branching needed here."""
    from halo_harness.headless import build_session
    build = build_session(cwd=cwd, bare=True, print_mode=True, max_turns=1)
    session = build.session

    def _call(system_text: str, user_text: str) -> str:
        from halo_harness import roles
        role_table = getattr(getattr(session, "agent_runtime", None), "role_table", None) or {}
        judge_ref, _profile, _effort, _source = roles.resolve_role_ref(
            "judge", role_table=role_table, parent_ref=session.model_ref,
            parent_profile=session.provider_profile, state_dir=session.state_dir
            if hasattr(session, "state_dir") else None)
        return session.call_small_model(system_text=system_text, user_text=user_text,
                                          max_tokens=200, timeout_s=60.0, model_ref=judge_ref)
    return _call


def propose_fix(evidence_text: str, config_entry: dict, *, cwd: Path,
                 model_call: "Optional[Callable[[str, str], str]]" = None) -> Optional[FixProposal]:
    """The evidence block + the masked config entry, to the model, with
    the fixed prompt above -- `model_call` is an injectable `(system_text,
    user_text) -> reply` seam (tests pass a mock; production leaves it
    None and gets `_default_model_call(cwd)`). Never raises: a model-call
    failure is reported as `None` (no proposal), same "a flaky call must
    never crash the diagnosis" rule every other judge-role call in this
    codebase already follows."""
    if model_call is None:
        model_call = _default_model_call(cwd)
    user_text = (f"{evidence_text}\n\nThe server's resolved config entry:\n"
                 f"{json.dumps(config_entry, indent=2, ensure_ascii=False)}")
    try:
        reply = model_call(FIX_SYSTEM_PROMPT, user_text)
    except Exception as e:
        return FixProposal(kind="other", detail=f"the model call failed: {type(e).__name__}: {e}", raw_text="")
    return parse_fix_proposal(reply)


# ---- applying a proposal (config_edit / path / url only) --------------------

def _apply_config_edit(raw_entry: dict, key: str, value: str) -> dict:
    """`key` is either a bare top-level key (`"timeout"`), or `env.<NAME>`/
    `headers.<NAME>` to set one entry inside that sub-dict -- the one
    nesting shape the fixed prompt documents (`env.<NAME>=<value>`)."""
    entry = dict(raw_entry)
    if "." in key:
        parent, _, child = key.partition(".")
        sub = dict(entry.get(parent) or {})
        sub[child] = value
        entry[parent] = sub
    else:
        entry[key] = value
    return entry


def apply_fix(proposal: FixProposal, *, name: str, cfg, cwd: Path) -> "tuple[bool, str]":
    """Mechanically applies `proposal` to its on-disk entry -- ONLY for
    the three mechanical kinds (config_edit/path/url); `install`/`env`/
    `other` are always advisory (the exact command/var name is shown, per
    `mcp_cli.install_hint`'s own "the line is for the user to run"
    contract -- never auto-executed, never auto-set in the user's shell).
    `(changed, message)`; `changed` is False whenever nothing was
    actually written (advisory kinds, or a write failure)."""
    if proposal.kind == "install":
        return False, f"nothing applied automatically -- run this yourself: {proposal.detail}"
    if proposal.kind == "env":
        return False, f"nothing applied automatically -- set this yourself: {proposal.detail}"
    if not proposal.mechanically_appliable:
        return False, f"could not classify a mechanically-appliable fix from: {proposal.raw_text!r}"

    # mcp_cli.py already owns the one read-modify-write implementation per
    # scope (indent/BOM/trailing-newline preservation for ~/.claude.json,
    # the sha256 approval-key convention) -- reused directly rather than
    # re-implemented a second time here.
    from halo_harness import mcp_cli
    raw_entry = mcp_cli._raw_entry_for(scope=cfg.scope, name=name, cwd=Path(cwd))
    if not raw_entry:
        return False, f"could not re-read {name}'s on-disk entry ({cfg.scope} scope) to edit it"

    if proposal.kind == "config_edit":
        key, sep, value = proposal.detail.partition("=")
        key = key.strip()
        if not sep or not key:
            return False, f"could not parse a key=value fix from: {proposal.detail!r}"
        new_entry = _apply_config_edit(raw_entry, key, value.strip())
    elif proposal.kind == "path":
        new_entry = dict(raw_entry)
        new_entry["command"] = proposal.detail.strip()
    else:  # "url"
        new_entry = dict(raw_entry)
        new_entry["url"] = proposal.detail.strip()

    try:
        mcp_cli._store_entry(scope=cfg.scope, name=name, entry=new_entry, cwd=Path(cwd))
    except (OSError, ValueError) as e:
        return False, f"could not write the fix to {cfg.scope} scope: {type(e).__name__}: {e}"
    return True, f"applied {proposal.raw_text!r} to {name}'s {cfg.scope}-scope entry"


# ---- the per-server "last diagnosis" record (deliverable 4) ----------------

@dataclass
class DiagnosisResult:
    server: str
    at: float
    verdict: str                       # "healthy" | "failed"
    evidence: str
    proposal: Optional[FixProposal]
    via_model: bool                     # False iff a learned-rule replay skipped the model entirely
    applied: bool
    message: str

    def summary_line(self) -> str:
        """Deliverable 4: "/mcp shows ... the last diagnosis per server
        (one line: when, the verdict, the fix proposed or applied)"."""
        when = time.strftime("%Y-%m-%d %H:%M:%S", time.localtime(self.at))
        if self.verdict == "healthy":
            return f"{when}: healthy"
        if self.proposal is None:
            return f"{when}: failed -- no fix proposed"
        verb = "applied" if self.applied else "proposed"
        replay = " (learned, no model call)" if not self.via_model else ""
        return f"{when}: failed -- {verb}: {self.proposal.raw_text}{replay}"


def _diagnosis_path(state_dir) -> Path:
    return Path(state_dir) / "mcp-diagnosis.json"


def load_last_diagnoses(state_dir) -> dict:
    """Never raises -- a missing/corrupt file degrades to "nothing
    diagnosed yet", same contract `providers.learned_rules.load_learned_
    rules` already follows for its own file."""
    try:
        data = json.loads(_diagnosis_path(state_dir).read_text(encoding="utf-8"))
        return data if isinstance(data, dict) else {}
    except (OSError, ValueError):
        return {}


def record_diagnosis(state_dir, result: DiagnosisResult) -> None:
    """Persists the COMPACT summary only (when/verdict/proposal/applied) --
    never the full evidence block (that already printed to the live
    caller; keeping it off disk indefinitely is one less place a masked-
    but-not-perfectly-scrubbed stderr tail could linger). Best-effort,
    idempotent read-modify-write, same tmp+os.replace pattern every other
    small JSON store in this harness uses."""
    path = _diagnosis_path(state_dir)
    data = load_last_diagnoses(state_dir)
    data[result.server] = {
        "at": result.at, "verdict": result.verdict,
        "proposal": result.proposal.to_dict() if result.proposal else None,
        "via_model": result.via_model, "applied": result.applied,
    }
    try:
        path.parent.mkdir(parents=True, exist_ok=True)
        tmp = path.with_name(path.name + f".tmp{os.getpid()}")
        tmp.write_text(json.dumps(data, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
        os.replace(tmp, path)
    except OSError:
        pass


def last_diagnosis_line(state_dir, name: str) -> Optional[str]:
    """`/mcp`'s own per-row line -- `None` when this server has never been
    deep-dived (nothing to show, never a fabricated placeholder)."""
    row = load_last_diagnoses(state_dir).get(name)
    if not row:
        return None
    when = time.strftime("%Y-%m-%d %H:%M:%S", time.localtime(row.get("at") or 0))
    if row.get("verdict") == "healthy":
        return f"last deep dive: {when} -- healthy"
    proposal = row.get("proposal")
    if not proposal:
        return f"last deep dive: {when} -- failed, no fix proposed"
    verb = "applied" if row.get("applied") else "proposed"
    replay = " (learned)" if not row.get("via_model", True) else ""
    return f"last deep dive: {when} -- {verb}: {proposal.get('raw_text', '?')}{replay}"


# ---- shared resolution helpers ----------------------------------------------

def resolve_tool_env(cwd: Path, settings=None) -> dict:
    """The exact child env a real connect to this directory's servers
    would use -- same construction `mcp_setup.build_manager` already does
    (`tool_child_env(base_env)`), reused here so the deep probe's `spawn`/
    `env_diff` steps see what a real session actually would."""
    from halo_harness.providers.config import tool_child_env
    base_env = settings.effective_env if settings is not None else dict(os.environ)
    return tool_child_env(base_env)


def resolve_one_config(name: str, *, cwd: Path, settings=None):
    """A fresh, freshly re-read-from-disk `McpServerConfig` for `name` --
    `None` if it no longer resolves to anything. Used both to resolve the
    server BEFORE the first probe and to re-resolve it after `apply_fix`
    edited its on-disk entry (an in-memory `McpServerConfig` object is
    immutable-by-convention here; the retest must see the EDITED file, not
    the stale pre-edit object)."""
    from halo_harness.config.claude_json import load_claude_json
    from halo_harness.mcp.manager import resolve_server_configs
    from halo_harness.mcp_setup import load_mcp_approvals
    try:
        resolved, _notices = resolve_server_configs(cwd=Path(cwd), claude_json=load_claude_json(), settings=settings,
                                                      approvals=load_mcp_approvals())
    except Exception:
        return None
    return resolved.get(name)


def select_failing_targets(cwd: Path, settings=None) -> "list[str]":
    """No `name` given on the CLI/`/mcp` -- every server currently
    `failed`/`needs_auth`, via the SAME live health check `halo mcp list`
    runs (`mcp_setup.build_manager`, `start=True`), closed immediately
    after reading its `status()` -- the deep probe itself always opens its
    OWN independent connection per target afterward (`doctor_probe.
    probe_server`), never reuses this manager's handles."""
    from halo_harness.config.claude_json import load_claude_json
    from halo_harness.mcp_setup import build_manager
    manager, _notices = build_manager(cwd=Path(cwd), claude_json=load_claude_json(), settings=settings,
                                        print_mode=False, start=True)
    if manager is None:
        return []
    try:
        return [r["name"] for r in manager.status() if r["state"] in ("failed", "needs_auth")]
    finally:
        manager.close_all()


# ---- the one entry point: probe -> propose-or-replay -> maybe apply --------

def diagnose(name: str, cfg, *, cwd: Path, tool_env: dict, state_dir, apply: bool = False,
             settings=None, model_call: "Optional[Callable[[str, str], str]]" = None,
             abort=None) -> DiagnosisResult:
    """Deliverables 2+3: probe `cfg`, and if it fails, either REPLAY a fix
    already proven for this exact failure signature (no model call, no
    "yes" needed -- it already earned that the first time: "fixed
    automatically next time") or PROPOSE a fresh one via the model.
    `apply` is the explicit yes for a FRESH proposal (the CLI's own
    `--apply`, a key in `/mcp`) -- a learned replay applies regardless of
    `apply`. A fix that worked (the re-test comes back healthy) is learned
    for next time; one that doesn't is reported, never silently retried.
    Always persists the compact summary via `record_diagnosis`; always
    returns, never raises."""
    from halo_harness.mcp import doctor_probe
    from halo_harness.providers.learned_rules import learn_mcp_fix, learned_mcp_fix

    probe = doctor_probe.probe_server(name, cfg, tool_env=tool_env, cwd=cwd, abort=abort)
    lines = [probe.evidence_text()]
    if probe.verdict == "healthy":
        result = DiagnosisResult(server=name, at=time.time(), verdict="healthy", evidence=probe.evidence_text(),
                                  proposal=None, via_model=False, applied=False, message="\n".join(lines))
        record_diagnosis(state_dir, result)
        return result

    sig = failure_signature(command=cfg.command, error_text=probe.primary_error_text())
    learned = learned_mcp_fix(state_dir, sig)
    via_model = learned is None
    if learned is not None:
        proposal = FixProposal.from_dict(learned)
        lines.append(f"replaying a previously-learned fix for this failure (no model call): "
                      f"{proposal.raw_text if proposal else '?'}")
    else:
        proposal = propose_fix(probe.evidence_text(), config_entry_for_prompt(cfg), cwd=cwd, model_call=model_call)
        lines.append(f"proposed fix: {proposal.raw_text}" if proposal else "the model proposed no classifiable fix.")

    applied = False
    # A learned replay already proved itself once -- the brief's own
    # "fixed automatically next time" -- so it applies with no fresh "yes"
    # needed; a FRESH model proposal only applies when the caller passed
    # `apply=True` (that IS the yes: `--apply` on the CLI, the apply key
    # in `/mcp`). Advisory kinds (install/env/other) are never applied
    # either way, by `apply_fix`'s own contract.
    should_apply = proposal is not None and proposal.mechanically_appliable and (apply or not via_model)
    if should_apply:
        ok, msg = apply_fix(proposal, name=name, cfg=cfg, cwd=cwd)
        lines.append(msg)
        if ok:
            fresh_cfg = resolve_one_config(name, cwd=cwd, settings=settings)
            if fresh_cfg is None:
                lines.append(f"{name}: applied the fix but could not re-resolve the config to re-test.")
            else:
                retest = doctor_probe.probe_server(name, fresh_cfg, tool_env=tool_env, cwd=cwd, abort=abort)
                lines.append(retest.evidence_text())
                applied = retest.verdict == "healthy"
                if applied:
                    learn_mcp_fix(state_dir, sig, proposal.to_dict())
                    lines.append(f"{name}: fixed and verified -- learned this fix for next time.")
                else:
                    lines.append(f"{name}: applied the fix, but the re-test still fails.")
    elif proposal is not None and not proposal.mechanically_appliable:
        lines.append("(advisory fix -- nothing for halo to apply automatically; see the line above)")

    result = DiagnosisResult(server=name, at=time.time(), verdict="failed", evidence=probe.evidence_text(),
                              proposal=proposal, via_model=via_model, applied=applied, message="\n".join(lines))
    record_diagnosis(state_dir, result)
    return result


# ---- corpus reader (deliverable 5) ------------------------------------------
# Directory layout (documented in docs/TROUBLESHOOTING.md's "MCP servers"
# section): one `<name>.log` (a copy of `~/.halo/mcp/<name>.log`) and/or
# one `<name>.test.txt` (captured stdout+stderr of `halo mcp test <name>`,
# or `halo mcp list`/`halo mcp fix <name>` -- any of them, same line
# shapes) per failing server; an optional `<name>.config.json` (that
# server's resolved entry, e.g. `halo mcp get <name>` reshaped, or the raw
# `.mcp.json`/`.claude.json` entry) feeds the model's proposal; an
# optional `bugreport.txt` (a full `halo bugreport` capture) is read for
# its own "MCP servers:" block (`bugreport._mcp_lines`'s exact rendered
# shape) as a fallback for any name with no `.test.txt` of its own.

_FAILURE_MARKERS = ("fail", "error", "refused", "not found", "traceback",
                     "timed out", "timeout", "unauthorized", "exception")


def _looks_like_failure(text: str) -> bool:
    return any(marker in (text or "").lower() for marker in _FAILURE_MARKERS)


def discover_corpus_servers(corpus_dir: Path) -> "list[str]":
    """Every server name this corpus directory has SOMETHING for -- a
    `.log`/`.test.txt`/`.config.json` file of its own, or a line in
    `bugreport.txt`'s "MCP servers:" block."""
    corpus_dir = Path(corpus_dir)
    names: "set[str]" = set()
    for suffix in (".log", ".test.txt", ".config.json"):
        for p in corpus_dir.glob(f"*{suffix}"):
            names.add(p.name[: -len(suffix)])
    bugreport = corpus_dir / "bugreport.txt"
    if bugreport.exists():
        try:
            text = bugreport.read_text(encoding="utf-8", errors="replace")
        except OSError:
            text = ""
        for m in re.finditer(r"^\s{2}(\S+):\s+(\w+)(?:\s+--\s+(.*))?$", text, re.MULTILINE):
            names.add(m.group(1))
    return sorted(names)


def _corpus_probe_result(corpus_dir: Path, name: str):
    from halo_harness.mcp.doctor_probe import ProbeResult, ProbeStep
    corpus_dir = Path(corpus_dir)
    steps: "list[ProbeStep]" = []

    log_path = corpus_dir / f"{name}.log"
    if log_path.exists():
        try:
            tail = "\n".join(log_path.read_text(encoding="utf-8", errors="replace").splitlines()[-20:])
        except OSError as e:
            tail = f"could not read {log_path.name}: {type(e).__name__}: {e}"
        steps.append(ProbeStep("corpus_log", not _looks_like_failure(tail), 0.0, tail or "(empty log)"))

    test_path = corpus_dir / f"{name}.test.txt"
    if test_path.exists():
        try:
            text = test_path.read_text(encoding="utf-8", errors="replace").strip()
        except OSError as e:
            text = f"could not read {test_path.name}: {type(e).__name__}: {e}"
        steps.append(ProbeStep("corpus_test_output", not _looks_like_failure(text), 0.0, text or "(empty)"))

    bugreport = corpus_dir / "bugreport.txt"
    if bugreport.exists():
        try:
            text = bugreport.read_text(encoding="utf-8", errors="replace")
        except OSError:
            text = ""
        m = re.search(rf"^\s{{2}}{re.escape(name)}:\s+(\w+)(?:\s+--\s+(.*))?$", text, re.MULTILINE)
        if m:
            state, err = m.group(1), (m.group(2) or "")
            steps.append(ProbeStep("corpus_bugreport", state == "connected", 0.0,
                                     f"{state}" + (f" -- {err}" if err else "")))

    if not steps:
        steps.append(ProbeStep("corpus", False, 0.0,
                                 "no captured log/test-output/bugreport line found for this name"))
    return ProbeResult(server=name, steps=steps)


def diagnose_from_corpus(corpus_dir: Path, names: "Optional[list]" = None, *,
                          model_call: "Optional[Callable[[str, str], str]]" = None) -> "list[DiagnosisResult]":
    """`halo doctor --mcp deep --from <dir>` -- reads captured evidence
    instead of probing a live server (there isn't one: the owner's real
    failures, fed from a different box entirely) and still runs the SAME
    propose step over each one's reconstructed evidence. Never applies
    (nothing to re-test against) and never persists a `last_diagnosis`
    record (this box's own `mcp-diagnosis.json` has nothing to do with the
    corpus's origin machine)."""
    corpus_dir = Path(corpus_dir)
    targets = names if names else discover_corpus_servers(corpus_dir)
    results: "list[DiagnosisResult]" = []
    for name in targets:
        probe = _corpus_probe_result(corpus_dir, name)
        if probe.verdict == "healthy":
            results.append(DiagnosisResult(server=name, at=time.time(), verdict="healthy",
                                             evidence=probe.evidence_text(), proposal=None, via_model=False,
                                             applied=False, message=probe.evidence_text()))
            continue
        config_entry: dict = {}
        config_path = corpus_dir / f"{name}.config.json"
        if config_path.exists():
            try:
                config_entry = json.loads(config_path.read_text(encoding="utf-8"))
            except (OSError, ValueError):
                config_entry = {}
        proposal = propose_fix(probe.evidence_text(), config_entry, cwd=corpus_dir, model_call=model_call)
        message = probe.evidence_text() + "\n" + (f"proposed fix: {proposal.raw_text}" if proposal
                                                     else "the model proposed no classifiable fix.")
        results.append(DiagnosisResult(server=name, at=time.time(), verdict="failed", evidence=probe.evidence_text(),
                                         proposal=proposal, via_model=True, applied=False, message=message))
    return results
