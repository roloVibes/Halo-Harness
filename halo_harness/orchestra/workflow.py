"""halo_harness.orchestra.workflow -- the Orchestra's fixed workflow graph,
designed in code before anything runs.

    goal -> lead -> split -> worker-1..N -> merge -> test -> gate -> done
                                  ^------------- loop ----------'

One worker step per lane (lane = 1..N); the merge takes the workers' pieces
one at a time; the gate either finishes the run or sends a failed piece back
to its worker along that worker's `loop` edge. 3.0.9.0: a lane that runs
after other lanes (orchestra/handoff_spec.py) hangs off them by an `after`
edge (`{"from": "worker-1", "to": "worker-2", "kind": "after", "label":
"summary"}`) instead of off the split, and every worker step carries its
`layer` (0 = the parallel layer); with nothing declared the graph is the
one above, with no `layer` field. 3.0.9.0 R2: a review run (`plan: review`)
holds its split step `planned` until the edited plan is approved;
`validate_plan(jobs)` (orchestra/plan_check.py) checks that plan. Everything here is plain,
JSON-serialisable data (Studio draws it); every helper returns a NEW graph
and never mutates its argument.
"""

from __future__ import annotations

import copy
from dataclasses import asdict, dataclass
from typing import Optional

from halo_harness.work.states import STATES as UNIT_STATES

KINDS = ("goal", "lead", "split", "worker", "merge", "test", "gate", "done")
# a step's words: the unit machine's (work/states.py, 3.1.2.0 R1) plus planned (3.0.9.0 R2, the split waits for review)
STATES = tuple(s for s in UNIT_STATES if s in ("pending", "running", "done", "failed", "skipped")) + ("planned",)
EDGE_KINDS = ("flow", "loop", "after")
MAX_WORKERS = 50

_LABELS = {
    "goal": "the goal", "lead": "lead orchestrator", "split": "split into jobs",
    "merge": "merge one at a time", "test": "run the tests", "gate": "quality gate",
    "done": "finished branch + report",
}


@dataclass
class Step:
    """One node. `lane` is the worker number for worker steps, else None."""
    id: str
    kind: str
    lane: Optional[int] = None
    state: str = "pending"
    label: str = ""

    def to_dict(self) -> dict:
        return asdict(self)

    @classmethod
    def from_dict(cls, data: dict) -> "Step":
        return cls(id=str(data["id"]), kind=str(data["kind"]), lane=data.get("lane"),
                   state=str(data.get("state") or "pending"), label=str(data.get("label") or ""))


def worker_id(lane: int) -> str:
    """The step id of worker `lane` (1-based)."""
    return f"worker-{int(lane)}"


def designed_graph(workers: int, after: Optional[dict] = None, labels: Optional[dict] = None) -> dict:
    """The fixed graph for `workers` lanes (1..50):
    `{"workers": N, "steps": [Step dicts], "edges": [{"from","to","kind"}]}`.
    `after` = `{lane: [upstream lanes]}` puts a lane in the layer below its
    upstreams (`labels[(upstream, lane)]` names what the edge carries); the
    graph then has `layers` = `[[lanes of layer 0], [layer 1], ...]`.
    Raises ValueError for a worker count outside 1..50."""
    if isinstance(workers, bool) or not isinstance(workers, int) or not 1 <= workers <= MAX_WORKERS:
        raise ValueError(f"workers must be a whole number from 1 to {MAX_WORKERS}, got {workers!r}")
    ups = {int(k): [int(u) for u in v if 1 <= int(u) <= workers and int(u) != int(k)] for k, v in (after or {}).items()}
    ups = {k: v for k, v in ups.items() if v and 1 <= k <= workers}
    steps = [Step(k, k, label=_LABELS[k]) for k in ("goal", "lead", "split")]
    steps += [Step(worker_id(i), "worker", lane=i, label=f"worker {i}") for i in range(1, workers + 1)]
    steps += [Step(k, k, label=_LABELS[k]) for k in ("merge", "test", "gate", "done")]
    edges = [_edge("goal", "lead"), _edge("lead", "split")]
    for i in range(1, workers + 1):
        if i in ups:
            edges += [dict(_edge(worker_id(u), worker_id(i), "after"), label=str((labels or {}).get((u, i)) or "after"))
                      for u in ups[i]]
        else:
            edges.append(_edge("split", worker_id(i)))
        edges.append(_edge(worker_id(i), "merge"))
    edges += [_edge("merge", "test"), _edge("test", "gate"), _edge("gate", "done")]
    edges += [_edge("gate", worker_id(i), "loop") for i in range(1, workers + 1)]
    graph = {"workers": workers, "steps": [s.to_dict() for s in steps], "edges": edges}
    if ups:
        layer = lane_layers(workers, ups)
        for s in graph["steps"]:
            if s["kind"] == "worker":
                s["layer"] = layer[s["lane"]]
        graph["layers"] = [[n for n in range(1, workers + 1) if layer[n] == d] for d in range(max(layer.values()) + 1)]
    return graph


def with_layers(graph: dict, after: dict, labels: Optional[dict] = None) -> dict:
    """`graph` redesigned with `after` (designed_graph), every step's state kept."""
    new = designed_graph(int(graph.get("workers") or 1), after, labels)
    states = {s.get("id"): s.get("state") for s in graph.get("steps") or []}
    for s in new["steps"]:
        s["state"] = states.get(s["id"]) or s["state"]
    return new


def lane_layers(workers: int, ups: dict) -> dict:
    """`{lane: layer}` for lanes 1..workers given `{lane: [upstream lanes]}`."""
    from halo_harness.orchestra.handoff_spec import layers
    deps = {str(n): [str(u) for u in ups.get(n, [])] for n in range(1, workers + 1)}
    return {int(k): v for k, v in layers(deps).items()}


def _edge(src: str, dst: str, kind: str = "flow") -> dict:
    return {"from": src, "to": dst, "kind": kind}


def step(graph: dict, step_id: str) -> dict:
    """The step dict with this id. Raises KeyError when there is none."""
    for s in graph.get("steps") or []:
        if s.get("id") == step_id:
            return s
    raise KeyError(f"no step {step_id!r} in this workflow")


def steps_of_kind(graph: dict, kind: str) -> list:
    """Every step dict of one kind, in graph order."""
    return [s for s in graph.get("steps") or [] if s.get("kind") == kind]


def advance(graph: dict, step_id: str, state: str) -> dict:
    """A copy of `graph` with step `step_id` set to `state`.
    Raises KeyError for an unknown step, ValueError for an unknown state."""
    if state not in STATES:
        raise ValueError(f"state must be one of {', '.join(STATES)}, got {state!r}")
    new = copy.deepcopy(graph)
    step(new, step_id)["state"] = state
    return new


def loop_back(graph: dict, lane: int) -> dict:
    """The gate sent lane `lane`'s piece back: that worker goes to pending
    again, and merge/test/gate/done return to pending behind it."""
    new = advance(graph, worker_id(lane), "pending")
    for kind in ("merge", "test", "gate", "done"):
        for s in steps_of_kind(new, kind):
            s["state"] = "pending"
    return new


def predecessors(graph: dict, step_id: str) -> list:
    """Ids with a `flow` or `after` edge into `step_id` (loop edges are not prerequisites)."""
    return [e["from"] for e in graph.get("edges") or [] if e.get("to") == step_id and e.get("kind") in ("flow", "after")]


def ready(graph: dict) -> list:
    """Ids of pending steps whose every flow predecessor is done or skipped."""
    finished = {s["id"] for s in graph.get("steps") or [] if s.get("state") in ("done", "skipped")}
    out = []
    for s in graph.get("steps") or []:
        if s.get("state") == "pending" and all(p in finished for p in predecessors(graph, s["id"])):
            out.append(s["id"])
    return out


def summary(graph: dict) -> dict:
    """`{state: count}` over every step, for a one-line status."""
    counts: dict = {}
    for s in graph.get("steps") or []:
        counts[s.get("state", "pending")] = counts.get(s.get("state", "pending"), 0) + 1
    return counts


def validate_graph(graph) -> list:
    """Plain-English problems with a loaded workflow.json; [] means usable."""
    if not isinstance(graph, dict):
        return ["workflow.json must be a JSON object"]
    problems = []
    ids = set()
    for i, s in enumerate(graph.get("steps") or []):
        if not isinstance(s, dict) or not s.get("id"):
            problems.append(f"steps[{i}] has no id")
            continue
        ids.add(s["id"])
        if s.get("kind") not in KINDS:
            problems.append(f"step {s['id']!r} has an unknown kind {s.get('kind')!r}")
        if s.get("state") not in STATES:
            problems.append(f"step {s['id']!r} has an unknown state {s.get('state')!r}")
    for e in graph.get("edges") or []:
        if not isinstance(e, dict) or e.get("from") not in ids or e.get("to") not in ids:
            problems.append(f"edge {e!r} points at a step that does not exist")
        elif e.get("kind") not in EDGE_KINDS:
            problems.append(f"edge {e['from']}->{e['to']} has an unknown kind {e.get('kind')!r}")
    return problems


from halo_harness.orchestra.plan_check import plan_problems, validate_plan  # noqa: E402,F401  (3.0.9.0 R2)
