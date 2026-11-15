"""halo_harness.providers.ollama_measure_guard -- Halo 3.6.0.0 R8 fix pass S5: a measurement (the ladder of loads
that finds the largest window wholly on a server's card) is one at a time per server, across every Halo process on
this machine, and it leaves the server as it found it.

    with measuring(host, model, state_dir) as g:
        if not g.ok:
            return g.say          # another measurement holds that server: one plain line, nothing was loaded
        ... the ladder of loads (providers/ollama_calibrate_steps.run_calibration) ...
    g.left                        # what it did afterwards and what it left, in one line

The lock is `<state>/ollama-measure/<server>.lock` (an advisory OS lock, held by the measuring process or thread and
let go when it ends or dies), with `<server>.json` beside it naming the model and the time for the line the next one
sees. Before the ladder, one `/api/ps` read records what was loaded and at which window; afterwards the measured
model is loaded back at the window it had (the ladder's last step left it at another window with every layer
forced onto the card) or unloaded when it was not loaded, and every other model the ladder moved off the card is
loaded back at its window. When the first read was not Ollama's answer nothing is restored, and the line says so;
when the read after the ladder is not, only the measured model is put back and the line says the others were not
checked.
"""

from __future__ import annotations

import hashlib
import json
import os
import time
from pathlib import Path
from typing import Optional


def lock_path(state_dir, host) -> Path:
    key = hashlib.sha1(str(getattr(host, "url", "")).rstrip("/").encode("utf-8")).hexdigest()[:16]
    return Path(state_dir) / "ollama-measure" / f"{key}.lock"


def _resident(host) -> "Optional[dict]":
    """{model: window} from one `/api/ps` read, or None when the answer was not Ollama's (unknown)."""
    from halo_harness.providers.ollama import request_json
    from halo_harness.providers.ollama_hw import ps_rows
    rows = ps_rows(request_json(host, "/api/ps", timeout=10.0).body)
    if rows is None:
        return None
    return {str(r.get("model") or r.get("name")): r.get("context_length") for r in rows if r.get("model") or r.get("name")}


def _find(models: dict, model: str) -> Optional[str]:
    from halo_harness.providers.ollama import ollama_names_match
    return next((m for m in models if ollama_names_match(m, model)), None)


class measuring:  # noqa: N801 -- used as `with measuring(...) as g`
    def __init__(self, host, model: str, state_dir):
        self.host, self.model, self.state_dir = host, model, state_dir
        self.ok, self.say, self.left, self.before = False, "", "", None
        self._fh = None

    def __enter__(self) -> "measuring":
        from halo_harness.filelock import _try_lock
        path = lock_path(self.state_dir, self.host)
        info = path.with_suffix(".json")
        try:
            path.parent.mkdir(parents=True, exist_ok=True)
            self._fh = open(path, "a+b")
        except OSError as e:
            self.say = f"the measurement of {self.model} on {self.host.name} did not start: {e}"
            return self
        if not _try_lock(self._fh):
            self._fh.close()
            self._fh = None
            try:
                held = json.loads(info.read_text(encoding="utf-8"))
            except (OSError, ValueError):
                held = {}
            since = time.strftime("%H:%M", time.localtime(held["at"])) if isinstance(held.get("at"), (int, float)) else "?"
            self.say = (f"a measurement on {self.host.name} is running already ({held.get('model') or 'a model'}, since "
                        f"{since}): {self.model} was not measured and nothing was loaded; measure it when that one ends")
            return self
        try:
            info.write_text(json.dumps({"model": self.model, "at": time.time(), "pid": os.getpid()}), encoding="utf-8")
        except OSError:
            pass
        self.ok = True
        self.before = _resident(self.host)
        return self

    def __exit__(self, *exc) -> None:
        if not self.ok:
            return
        try:
            self.left = self._restore()
        except Exception as e:  # noqa: BLE001 -- the line says what broke
            self.left = f"{self.host.name} was not put back as it was: {type(e).__name__}: {e}"
        finally:
            from halo_harness.filelock import _unlock
            try:
                lock_path(self.state_dir, self.host).with_suffix(".json").unlink()
            except OSError:
                pass
            _unlock(self._fh)
            self._fh.close()
            self._fh = None

    def _restore(self) -> str:
        from halo_harness.providers.ollama_load import load, unload
        host, model, before = self.host, self.model, self.before
        if before is None:
            return (f"left {host.name} with {model} as the last step loaded it (what was loaded before the measurement "
                    "could not be read, so nothing was put back)")
        after = _resident(host)  # fix pass F3: unreadable is unknown, never "nothing is loaded"
        done, oks = [], []
        mine = _find(before, model)
        if mine is not None and isinstance(before[mine], int):
            got = load(host, model, num_ctx=before[mine], window_from="the window it had")
            done.append(f"{model} back at {before[mine]:,}, as it was" if got["ok"] else got["say"])
            oks.append(got["ok"])
        elif mine is not None:
            got = load(host, model)
            done.append(f"{model} loaded again, as it was" if got["ok"] else got["say"])
            oks.append(got["ok"])
        else:
            got = unload(host, model)
            done.append(f"{model} unloaded (it was not loaded before)" if got["ok"] else got["say"])
            oks.append(got["ok"])
        others = [m for m in before if m != mine]
        if after is None and others:
            oks.append(False)
            done.append(f"the other models ({', '.join(others)}) were not checked: {host.name} did not give a readable "
                        "/api/ps after the measurement")
            others = []
        for other in others:
            window = before[other]
            if _find(after, other) is not None and after.get(_find(after, other)) == window:
                continue
            got = load(host, other, num_ctx=window if isinstance(window, int) else None,
                       window_from="the window it had")
            done.append(f"{other} loaded back at {window:,} (the measurement had moved it off the card)"
                        if got["ok"] and isinstance(window, int) else got["say"])
            oks.append(got["ok"])
        head = f"left {host.name} as it found it" if all(oks) else f"tried to leave {host.name} as it found it"
        return f"{head}: " + "; ".join(done)
