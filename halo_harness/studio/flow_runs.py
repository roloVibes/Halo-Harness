"""halo_harness.studio.flow_runs -- the one flow run Studio drives (Halo
3.0.4.0 round R5), the shape of orchestra_live.py.

`start(run_dir, ...)` runs `flows.run.run()` on a daemon thread with the
adapters `factory(**kwargs)` makes (None = the real `flows.adapters.Adapters`;
the kwargs are `model`, `auto_accept`, `state_dir`, `cwd`), so no request
thread ever waits on a model, a render or a human gate. A second thread
tails the run's `events.jsonl` every `TAIL_S` seconds and publishes each
state / step / gate / post / metric / report line on Studio's live feed as
`flow_<kind>` with `session_id: "flow:<run id>"` and the line plus `run` as
data (`note` lines stay in the file). One run at a time: `live_id()` names
it while it runs. A resume is the same `start` on an existing folder.
"""

from __future__ import annotations

import threading
import time
from pathlib import Path
from typing import Callable, Optional

from halo_harness.flows import state

TAIL_S = 0.25
_lock = threading.Lock()
_live: dict = {}


def live_id() -> Optional[str]:
    with _lock:
        t = _live.get("thread")
        return _live.get("run") if t is not None and t.is_alive() else None


def frame_of(run: str, entry: dict) -> Optional[dict]:
    kind = state.FEED_KINDS.get(entry.get("kind"))
    if kind is None:
        return None
    return {"session_id": f"flow:{run}", "event": kind, "data": dict(entry, run=run),
            "turn": None, "agent_id": None, "ts": entry.get("ts") or time.time()}


def tail(run_dir: Path, publish: Callable, done: threading.Event, since: int = 0) -> None:
    """Publish every new line until `done` is set, then the last ones."""
    seen = since
    while True:
        finished = done.is_set()
        for entry in state.read_events(run_dir, since=seen):
            seen += 1
            frame = frame_of(run_dir.name, entry)
            if frame is not None:
                try:
                    publish(frame)
                except Exception:
                    pass
        if finished:
            return
        done.wait(TAIL_S)


def _work(run_dir: Path, factory, kwargs: dict, done: threading.Event) -> None:
    try:
        if factory is None:
            from halo_harness.flows.adapters import Adapters as factory
        adapters = factory(**kwargs)
        from halo_harness.flows.run import run
        run(run_dir, adapters=adapters)
    except Exception as e:  # the run log says what went wrong; Studio stays up
        try:
            flow = state.Flow(run_dir)
            flow.update(status="stopped")
            flow.log("state", f"the runner stopped on an error: {type(e).__name__}: {e}", step=None,
                     error=f"{type(e).__name__}: {e}")
        except OSError:
            pass
    finally:
        done.set()


def start(run_dir, *, factory=None, model: Optional[str] = None, auto_accept: bool = False, state_dir=None,
          cwd=None, publish: Optional[Callable] = None) -> bool:
    """Start (or resume) the run on its threads; False when another run is still live."""
    run_dir = Path(run_dir)
    done = threading.Event()
    kwargs = {"model": model, "auto_accept": bool(auto_accept), "state_dir": state_dir,
              "cwd": str(cwd) if cwd is not None else None}
    since = len(state.read_events(run_dir))
    with _lock:
        t = _live.get("thread")
        if t is not None and t.is_alive():
            return False
        worker = threading.Thread(target=_work, args=(run_dir, factory, kwargs, done),
                                  name=f"halo-flow-{run_dir.name}", daemon=True)
        _live.update(run=run_dir.name, thread=worker, done=done, run_dir=run_dir)
        worker.start()
    if publish is not None:
        threading.Thread(target=tail, args=(run_dir, publish, done, since), name=f"halo-flow-feed-{run_dir.name}",
                         daemon=True).start()
    return True


def wait(timeout: float = 30.0) -> bool:
    """Tests: wait for the live run to end. True when it did."""
    with _lock:
        t = _live.get("thread")
    if t is None:
        return True
    t.join(timeout)
    return not t.is_alive()
