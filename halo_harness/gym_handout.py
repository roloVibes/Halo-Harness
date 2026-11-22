"""halo_harness.gym_handout -- 3.6.0.13 GM rules G1 and G2: does main hand work out more with the helpers words of
3.6.0.10 ("now") than without them ("before"), on a LOCAL model?

    ARMS = ("before", "now")
    start(ref, arm, folder, *, window=None, platform=None) -> (session, full tools, system text, messages, tools sent)
        an arm's first request, built by the measure's own stub (agent/prompt_measure._first_request) on Auto with the
        Builder, the job's words as the user's turn and the acceptEdits mode line after it; "before" turns the helpers
        words off before the start (today's line, the same tools), "now" is what a new Auto session sends
    resolve(ref_raw, *, state_dir) -> dict
        the host, route, profile and window a local ref is sent at (as gym_run resolves them), or an error
    trial(ref, arm, folder, *, host, route, profile, decision, state_dir, window=None, think_off=False) -> dict
        the project written again into `folder`, then at most 10 requests through gym_send.send_turn_for, every tool
        call answered by the gym's own table over the copy (no Session runs, helpers are never run, nothing asks)
    run_model(ref_raw, *, trials=3, state_dir) -> dict
        both arms' first requests built first (identical words: no trial, no request), then before 1, now 1,
        before 2, ...; the model unloaded at the end (keep_alive 0) on the Ollama route

A trial's counts use the one meaning of "itself" (agent/handout_kind.kind): a "handout" call earns at most ONE part,
the first in part order whose words it holds (case-blind; description, prompt, task), and when it holds two parts or
more it counts once as "bundled". Every request carries 4,096 reply tokens, and thinking is off where the route takes
it (an Ollama model whose catalog row says it thinks).
"""

from __future__ import annotations

import fnmatch
import os
import re
import shutil
import time
from pathlib import Path
from typing import Optional

from halo_harness import gym_handout_fixture as F

ARMS = ("before", "now")
MODE = "acceptEdits"
MAX_REQUESTS = 10
REPLY_TOKENS = 4096
_SHELLS = ("Bash", "PowerShell")
_MAX_LINES = 400


def start(ref, arm: str, folder, *, window: Optional[int] = None, platform: Optional[str] = None) -> tuple:
    if arm not in ARMS:
        raise ValueError(f"an arm is one of {ARMS}, not {arm!r}")
    from halo_harness.agent.prompt_measure import _first_request
    return _first_request(ref, window=window, platform=platform, cwd=Path(folder), control="auto", builder=True,
                          text=F.TASK, helpers_off=(arm == "before"), mode=MODE)


def _counts() -> dict:
    return {"parts": [], "calls": 0, "bundled": 0, "typed": 0, "named_right": 0, "own": 0, "proposals": 0,
            "finished": False, "requests": 0, "error": None}


def _fresh(folder: Path) -> None:
    folder.mkdir(parents=True, exist_ok=True)
    for child in list(folder.iterdir()):
        if child.is_dir() and not child.is_symlink():
            shutil.rmtree(child)
        else:
            child.unlink()


class _Table:
    """The trial's tools and its permission mode: the gym's own Read, Grep, Glob, Edit and Write over the copy (a path
    outside it refused), no command run, helpers answered with the fixed answers, nothing asks."""

    def __init__(self, folder: Path, session, state_dir, counts: dict):
        self.root = Path(folder).resolve()
        self.given = Path(os.path.abspath(folder))  # the copy as it was named (a short or linked spelling of root)
        self.session = session
        self.state_dir = state_dir
        self.counts = counts
        self.earned: set = set()

    def answer(self, name: str, args: dict) -> "tuple[str, bool]":
        from halo_harness.agent.handout_kind import kind
        args = args if isinstance(args, dict) else {}
        k = kind(name)
        if k == "handout":
            return self._handout(name, args)
        if k == "board":
            return F.BOARD, False
        self.counts["own"] += 1
        if name == "Builder":
            self.counts["proposals"] += 1
            return F.BUILDER, False
        if name == "AskUserQuestion":
            return F.ASK, False
        if name in _SHELLS:
            return (F.ANSWERS[2] if "test" in str(args.get("command") or "").lower() else F.NO_COMMANDS), False
        files = {"Read": self._read, "Write": self._write, "Edit": self._edit, "Glob": self._glob, "Grep": self._grep}
        if name in files:
            try:
                return files[name](args)
            except _Outside:
                return F.OUTSIDE, True
            except (OSError, ValueError, TypeError, AttributeError, KeyError, re.error, NotImplementedError) as e:
                return f"{name} failed: {e}", True  # an argument of a wrong type too: an answer, never a lost trial
        return F.NOT_RUN.format(name=name), True

    # helpers: the name check of agent/subagent.py run_agent_call, then the part match
    def _handout(self, name: str, args: dict) -> "tuple[str, bool]":
        c = self.counts
        c["calls"] += 1
        if name == "Workflow":
            flow = args.get("name")
            flow = flow if isinstance(flow, str) or not flow else str(flow)  # a name of a wrong type is a wrong name
            if flow:
                c["typed"] += 1
                from halo_harness.crew import flow_door
                if flow in flow_door.names(cwd=self.root, state_dir=self.state_dir):
                    c["named_right"] += 1
            words, label = str(args.get("task") or ""), str(args.get("description") or flow or "")
        else:
            given = args.get("subagent_type")
            given = given if isinstance(given, str) or not given else str(given)  # a wrong type: a wrong name, counted
            subagent_type = given or "general-purpose"
            if given:
                c["typed"] += 1
            agents = getattr(getattr(self.session, "agent_runtime", None), "agents", None) or {}
            if subagent_type not in agents:
                known = ", ".join(sorted(agents)) or "(none discovered)"
                return f"Unknown subagent_type {subagent_type!r}. Known types: {known}", True
            if given:
                c["named_right"] += 1
            words = " ".join(str(args.get(k) or "") for k in ("description", "prompt", "task"))
            label = str(args.get("description") or "")
        low = words.lower()
        hits = [i for i, part in enumerate(F.PARTS) if any(w.lower() in low for w in part)]
        if not hits:
            return F.NO_PART.format(description=label), False
        if hits[0] + 1 not in self.earned:
            self.earned.add(hits[0] + 1)
            c["parts"] = sorted(self.earned)
        if len(hits) > 1:
            c["bundled"] += 1
        return "\n".join(F.ANSWERS[i] for i in hits), False

    # the files: inside the copy only
    def _path(self, raw, *, default: bool = False) -> Path:
        if raw is None or str(raw).strip() == "":
            if default:
                return self.root
            raise ValueError("a path is required")
        text = str(raw)
        # Judged as text FIRST: a path that leaves the copy by its own letters (a network name, a root, `..` steps,
        # `~`) is refused before the OS is asked anything about it. On Windows, resolving a network name opens a
        # connection to the host it names, and the name comes from the model under test.
        if text.startswith(_NET):
            raise _Outside()
        p = Path(text).expanduser()
        lex = Path(os.path.normpath(p if p.is_absolute() else self.root / p))
        if not any(lex == base or lex.is_relative_to(base) for base in (self.root, self.given)):
            raise _Outside()
        p = lex.resolve()  # a link inside the copy that points outside it is caught here
        if p != self.root and not p.is_relative_to(self.root):
            raise _Outside()
        return p

    def _rel(self, p: Path) -> str:
        return p.relative_to(self.root).as_posix() if p != self.root else "."

    def _read(self, a: dict) -> "tuple[str, bool]":
        p = self._path(a.get("file_path"))
        if not p.is_file():
            return f"File does not exist: {self._rel(p)}", True
        lines = p.read_text(encoding="utf-8", errors="replace").splitlines()
        first = max(1, int(a.get("offset") or 1))
        last = first - 1 + max(1, int(a.get("limit") or 2000))
        out = [f"{n:>6}\t{line}" for n, line in enumerate(lines, 1) if first <= n <= last]
        return ("\n".join(out) if out else "(the file is empty)"), False

    def _write(self, a: dict) -> "tuple[str, bool]":
        p = self._path(a.get("file_path"))
        p.parent.mkdir(parents=True, exist_ok=True)
        p.write_text(str(a.get("content") or ""), encoding="utf-8", newline="\n")
        return f"Wrote {self._rel(p)}", False

    def _edit(self, a: dict) -> "tuple[str, bool]":
        p = self._path(a.get("file_path"))
        if not p.is_file():
            return f"File does not exist: {self._rel(p)}", True
        old, new = str(a.get("old_string") or ""), str(a.get("new_string") or "")
        text = p.read_text(encoding="utf-8", errors="replace")
        if not old or old == new:
            return "old_string must be given and differ from new_string", True
        n = text.count(old)
        if n == 0:
            return f"old_string was not found in {self._rel(p)}", True
        if n > 1 and not a.get("replace_all"):
            return f"old_string is found {n} times in {self._rel(p)}: give more context or set replace_all", True
        p.write_text(text.replace(old, new) if a.get("replace_all") else text.replace(old, new, 1), encoding="utf-8",
                     newline="\n")
        return f"Edited {self._rel(p)}", False

    def _inside(self, paths) -> list:
        out = []
        for q in paths:
            try:
                r = q.resolve()
            except OSError:
                continue
            if r.is_file() and (r == self.root or r.is_relative_to(self.root)):
                out.append(r)
        return sorted(set(out))

    def _glob(self, a: dict) -> "tuple[str, bool]":
        base = self._path(a.get("path"), default=True)
        pattern = str(a.get("pattern") or "*")
        if pattern.startswith(_NET + ("/", "\\", "~")) or Path(pattern).is_absolute() or ".." in Path(pattern).parts:
            raise _Outside()  # a pattern that climbs out of the copy or starts at a root lists nothing outside it
        found = self._inside(base.glob(pattern))
        return ("\n".join(self._rel(p) for p in found[:_MAX_LINES]) if found else "No files found"), False

    def _grep(self, a: dict) -> "tuple[str, bool]":
        base = self._path(a.get("path"), default=True)
        rx = re.compile(str(a.get("pattern") or ""), re.IGNORECASE if a.get("-i") else 0)
        glob = a.get("glob")
        files = [base] if base.is_file() else self._inside(base.rglob("*"))
        mode = a.get("output_mode") or "files_with_matches"
        out = []
        for p in files:
            rel = self._rel(p)
            if glob and not (fnmatch.fnmatch(p.name, glob) or fnmatch.fnmatch(rel, glob)):
                continue
            try:
                lines = p.read_text(encoding="utf-8").splitlines()
            except (OSError, UnicodeDecodeError):
                continue
            hits = [(n, line) for n, line in enumerate(lines, 1) if rx.search(line)]
            if not hits:
                continue
            if mode == "content":
                out += [f"{rel}:{n}:{line}" for n, line in hits]
            elif mode == "count":
                out.append(f"{rel}:{len(hits)}")
            else:
                out.append(rel)
        return ("\n".join(out[:_MAX_LINES]) if out else "No matches found"), False


class _Outside(Exception):
    pass


_NET = ("\\\\", "//")  # a network name, in either spelling


def trial(ref, arm: str, folder, *, host, route, profile, decision, state_dir, window: Optional[int] = None,
          think_off: bool = False) -> dict:
    from halo_harness.agent.derive import derive_request
    from halo_harness.agent.prompt_wire import shape
    from halo_harness.gym_send import send_turn_for
    folder = Path(folder)
    _fresh(folder)
    F.write(folder)
    session, _full, system_text, messages, sent = start(ref, arm, folder, window=window)
    counts = _counts()
    table = _Table(folder, session, state_dir, counts)
    extra = {"overrides": {"think": False}} if think_off and getattr(route, "provider", "") == "ollama" else {}
    for n in range(MAX_REQUESTS):
        if n:
            system_text, messages, tools = derive_request(session.log)
            system_text, messages, sent = shape(session, system_text, messages, list(tools or []), purpose="measure")
            sent = list(sent or [])
        result = send_turn_for(host=host, route=route, profile=profile, decision=decision, system_text=system_text,
                               messages=messages, tools=sent, requested_max_tokens=REPLY_TOKENS, state_dir=state_dir,
                               **extra)
        counts["requests"] += 1
        if result.error:
            counts["error"] = result.error
            break
        if not result.tool_blocks:
            counts["finished"] = True
            break
        calls = [(f"gym_{n + 1}_{i + 1}", b.get("name") or "", b.get("input") or {})
                 for i, b in enumerate(result.tool_blocks)]
        content = [{"type": "text", "text": result.text}] if result.text else []
        content += [{"type": "tool_use", "id": cid, "name": name, "input": args} for cid, name, args in calls]
        session.log.add(type="assistant", content=content)
        for cid, name, args in calls:
            text, is_error = table.answer(name, args)
            session.log.add(type="tool_result", tool_use_id=cid, content=text, is_error=is_error)
    return counts


def resolve(ref_raw: str, *, state_dir) -> dict:
    """{"ref", "model", "host_name", "digest", "host", "route", "profile", "decision", "window", "think_off",
    "error"} for a local ref (ol:, hf:local, hf:mlx), as gym_run resolves it; any other ref: its error only."""
    from halo_harness.model import parse_model_ref
    from halo_harness.providers.routing import Route
    ref = parse_model_ref(ref_raw)
    out = {"ref": ref, "model": ref.model, "host_name": "?", "digest": None, "host": None, "route": None,
           "profile": None, "decision": None, "window": None, "think_off": False, "error": None}
    if ref.provider == "huggingface" and (getattr(ref, "local", False) or getattr(ref, "mlx", False)):
        from halo_harness.gym_run import _resolve_huggingface_host
        from halo_harness.gym_send import HFContextDecision
        from halo_harness.model import resolve_model_profile
        host, stable_id, error = _resolve_huggingface_host(ref, ref_raw, state_dir)
        if error:
            return {**out, "host_name": "huggingface", "error": error}
        prof = resolve_model_profile(ref, state_dir)
        decision = HFContextDecision(num_ctx=prof.context_tokens, max_output_tokens=prof.max_output_tokens)
        return {**out, "host_name": "huggingface", "digest": stable_id, "host": host, "decision": decision,
                "route": Route(provider="huggingface", upstream_model=ref.model, dialect="openai-chat"),
                "window": decision.num_ctx}
    if ref.provider != "ollama":
        return {**out, "error": f"{ref_raw}: the gym runs local models only."}
    from halo_harness.providers.effort_on import _thinks
    from halo_harness.providers.ollama import get_catalog, resolve_ollama_host
    from halo_harness.providers.ollama_hw import catalog_row, resolve_context_decision
    from halo_harness.providers.profiles import resolve_profile
    host = resolve_ollama_host(ref.host)
    if host is None:
        return {**out, "host_name": ref.host or "?",
                "error": f"no configured Ollama host for {ref_raw!r} -- see `ollama.hosts` in ~/.halo/config.json"}
    row = catalog_row(get_catalog(host), ref.model) or {}
    decision = resolve_context_decision(ref)
    route = Route(provider="ollama", upstream_model=ref.model, dialect="ollama")
    return {**out, "host_name": host.name, "digest": row.get("digest"), "host": host, "route": route,
            "profile": resolve_profile(route, state_dir=state_dir), "decision": decision, "window": decision.num_ctx,
            "think_off": _thinks(row) is True}


def run_model(ref_raw: str, *, trials: int = 3, state_dir) -> dict:
    from halo_harness.gym_run import _scratch_dir
    r = resolve(ref_raw, state_dir=state_dir)
    card = {"model": r["model"], "model_ref": ref_raw, "host_name": r["host_name"], "digest": r["digest"],
            "trials": trials, "window": r["window"], "finished_at": None, "before": [], "now": [], "errors": []}
    if r["error"]:
        card["errors"].append(r["error"])
        card["finished_at"] = time.time()
        return card
    route = r["route"]
    window = r["window"] if route.provider == "huggingface" else None  # an ol: ref: the stub resolves it as a session
    with _scratch_dir(None) as folder:
        F.write(folder)
        first = {arm: start(ref_raw, arm, folder, window=window) for arm in ARMS}
        if first["before"][2] == first["now"][2] and first["before"][4] == first["now"][4]:
            return {"model": r["model"], "model_ref": ref_raw, "host_name": r["host_name"], "same_words": True}
        try:
            for i in range(trials):
                for arm in ARMS:
                    try:
                        got = trial(ref_raw, arm, folder, host=r["host"], route=route, profile=r["profile"],
                                    decision=r["decision"], state_dir=state_dir, window=window,
                                    think_off=r["think_off"])
                    except Exception as e:  # one broken trial never loses the others
                        got = {**_counts(), "error": f"{type(e).__name__}: {e}"}
                    card[arm].append(got)
                    if got["error"]:
                        card["errors"].append(f"{arm} {i + 1}: {got['error']}")
        finally:
            if route.provider == "ollama":
                try:
                    from halo_harness.providers.ollama_load import unload
                    got = unload(r["host"], r["model"])
                    if isinstance(got, dict) and not got.get("ok"):  # still loaded: the card says so
                        card["errors"].append(f"unload: {got.get('say') or 'the model was not unloaded'}")
                except Exception as e:
                    card["errors"].append(f"unload: {type(e).__name__}: {e}")
    card["finished_at"] = time.time()
    return card


# ---- G3, G6: what a person reads, and the cards apart from the battery's ------------------------------------------
HANDOUT_DIR_NAME = "gym-handout"  # never under gym/: gym.iter_results and models_best_at read gym/*/*.json
HEAD = "Main hands work out (halo gym handout):"
SAME_WORDS = ("{model}: not measured: this model is sent the same words before and today (it takes no tools, or "
              "today's words do not fit its window), so there is nothing to compare.")


def _times(n: int) -> str:
    return "three times" if n == 3 else f"{n} time{'' if n == 1 else 's'}"


def facts(trials: int = 3) -> list:
    """The four facts (what, cost, time, writes), one sentence each, printed before the first request."""
    return [f"Runs one fixed four-part job with each local model you name as main, {_times(trials)} with the words main "
            f"had before 3.6.0.10 and {_times(trials)} with today's, and counts the parts it hands to helpers, not "
            "whether the work is better. Helpers are not run: each gets a fixed answer.",
            "Free: local models only; nothing is sent to a cloud.",
            "About 20 to 40 minutes per model with three trials (not measured yet: the first run sets this line).",
            "A scratch copy of a small project, removed at the end, and one card per model under "
            "~/.halo/gym-handout/<host>/."]


def card_path(state_dir, host_name, digest, model=None) -> Path:
    """<state>/gym-handout/<host>/handout-<the name gym.result_path gives the digest>.json: one card per model and
    host; a new run replaces it."""
    from halo_harness import gym
    name = gym.result_path(state_dir, host_name, digest, model).stem
    return Path(state_dir) / HANDOUT_DIR_NAME / gym.host_slug(host_name) / f"handout-{name}.json"


def save_card(state_dir, card: dict) -> Path:
    """tmp + os.replace, as gym.save_result."""
    import json
    import os
    import threading
    path = card_path(state_dir, card.get("host_name"), card.get("digest"), card.get("model"))
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_name(f"{path.name}.{os.getpid()}-{threading.get_ident()}.tmp")
    tmp.write_text(json.dumps(card, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    os.replace(tmp, path)
    return path


def iter_cards(state_dir) -> list:
    """Every saved handout card, newest `finished_at` first; [] on any OSError (gym.iter_results' contract)."""
    from halo_harness.gym import load_result
    out = []
    try:
        for p in (Path(state_dir) / HANDOUT_DIR_NAME).glob("*/handout-*.json"):
            data = load_result(p)
            if data is not None:
                out.append(data)
    except OSError:
        return []
    out.sort(key=lambda c: c.get("finished_at") or 0, reverse=True)
    return out


def _num(x) -> str:
    """At most one decimal and no ".0"."""
    s = f"{x:.1f}"
    return s[:-2] if s.endswith(".0") else s


def _mean(trials: list, key) -> str:
    vals = [key(t) for t in trials]
    return _num(sum(vals) / len(vals) if vals else 0)


def line(card: dict) -> str:
    """The card's line (section 3), with the card's own `trials` where the line writes 3, and its errors line."""
    now, before = list(card.get("now") or []), list(card.get("before") or [])
    n = int(card.get("trials") or 0)
    total = lambda trials, key: sum(int(t.get(key) or 0) for t in trials)  # noqa: E731
    done = lambda trials: sum(1 for t in trials if t.get("finished"))  # noqa: E731
    calls = _mean(now, lambda t: int(t.get("calls") or 0))
    out = (f"{card.get('model')}: hands out {_mean(now, lambda t: len(t.get('parts') or []))} of 4 parts in "
           f"{calls} call{'' if calls == '1' else 's'} (before "
           f"{_mean(before, lambda t: len(t.get('parts') or []))}) · bundled {total(now, 'bundled')} · names right "
           f"{total(now, 'named_right')} of {total(now, 'typed')} · own steps {_mean(now, lambda t: int(t.get('own') or 0))} "
           f"(before {_mean(before, lambda t: int(t.get('own') or 0))}) · finished {done(now)} of {n} (before "
           f"{done(before)}) · {n} trial{'' if n == 1 else 's'}")
    if card.get("errors"):
        out += f"\n  errors during the run (non-fatal): {'; '.join(card['errors'])}"
    return out


__all__ = ["ARMS", "HANDOUT_DIR_NAME", "HEAD", "MAX_REQUESTS", "MODE", "REPLY_TOKENS", "SAME_WORDS", "card_path",
           "facts", "iter_cards", "line", "resolve", "run_model", "save_card", "start", "trial"]
