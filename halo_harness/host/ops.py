"""halo_harness.host.ops -- the host's typed fix vocabulary (Halo 3.3.7.0 R2; plans/local-model-fit-brief.md H10.1;
docs/HOST.md "The vocabulary"). Not a classifier: the interface. Every operation is a named request with typed
parameters, never a command line; each is previewable (`dry: true`), recorded, and the ones that change something
can be put back.

    Op(name, grant, params, preview, apply, stated, job, profile, help)
        params      {param: (type, required, help)} -- type "str" | "int" | "bool" | "any"
        preview     fn(ctx, p) -> {would: [...], writes: [...], takes: "~N s", cost: "local: time", breach?: line}
        apply       fn(ctx, p) -> {ok, say, ...} (a job-shaped op returns {ok, job})
        stated      True: a host-side server setting -- the answer is the exact line for the host's OS and
                    `applied: false`; nothing is changed or called
        profile     True: a Halo-side profile field (agent_proposals.land_user -> changes.record); such a request
                    names the finding it acts on (`evidence`) and the host verifies it (host/verify.py)
    table() -> {name: Op}   ops_control + ops_jobs + ops_manage; `admin` has no operation in this version
    Ctx(svc, hid, rec, body)  one request: the peer, its body, the Ollama host it names (`params.host`, a name this
                    host serves, or the only one), the model's profile key
    validate(op, params) -> (clean params, problems)
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Callable, Optional

TYPES = {"str": (str,), "int": (int,), "bool": (bool,), "any": (str, int, float, bool)}


@dataclass
class Op:
    name: str
    grant: str
    params: dict
    preview: Callable
    apply: Callable
    stated: bool = False
    job: bool = False
    profile: bool = False
    help: str = ""
    writes: list = field(default_factory=list)


def _typed(kind: str, v) -> bool:
    if kind == "int":
        return isinstance(v, int) and not isinstance(v, bool)
    return isinstance(v, TYPES.get(kind, (object,)))


def validate(op: Op, params) -> "tuple[dict, list]":
    params = params if isinstance(params, dict) else {}
    clean, problems = {}, []
    for k, (kind, required, help_) in op.params.items():
        v = params.get(k)
        if v is None or v == "":
            if required:
                problems.append(f"{k}: {help_}")
            continue
        if isinstance(v, float) and kind == "int" and v.is_integer():
            v = int(v)
        if not _typed(kind, v):
            problems.append(f"{k}: a {kind} ({help_})")
            continue
        clean[k] = v.strip() if isinstance(v, str) else v
    extra = sorted(set(params) - set(op.params))
    if extra:
        problems.append(f"{op.name} takes {', '.join(op.params) or 'no parameters'}, not {', '.join(extra)}")
    return clean, problems


class Ctx:
    def __init__(self, svc, hid: str, rec: Optional[dict], body: dict) -> None:
        self.svc, self.hid, self.rec, self.body = svc, hid, rec or {}, body
        self.home, self.view = svc.home, svc.view
        self.peer = str(self.rec.get("name") or hid[:8])
        ev = body.get("evidence") if isinstance(body.get("evidence"), dict) else None
        self.evidence = ev if ev and (ev.get("finding") or ev.get("lines")) else None
        self.why = str(body.get("why") or "")[:300]
        self.dry = body.get("dry") is True
        self.host = None

    def pick_host(self, params: dict) -> Optional[str]:
        """Sets self.host from `params.host` (a served name) or `params.port`; the reason when it cannot."""
        hs = self.view.hosts()
        name, port = str(params.get("host") or "").strip(), params.get("port")
        if name:
            hit = [h for h in hs if h.name.lower() == name.lower()]
        elif isinstance(port, int):
            from halo_harness.host.state import port_of
            hit = [h for h in hs if port_of(h.url) == port]
        else:
            hit = hs if len(hs) == 1 else []
        if not hit:
            served = ", ".join(h.name for h in hs) or "none"
            return (f"this host serves {served}; name one with params.host" if not name else
                    f"this host serves no Ollama host named {name!r} (it serves {served})")
        self.host = hit[0]
        return None

    def key(self, model: str) -> str:
        from halo_harness.ollama_steward.profiles import key_for
        return key_for(self.host.name, model)

    def scope(self) -> str:
        """The request's scope; else until-restart for a fix that cites a finding (the steward), keep for a person."""
        from halo_harness.ollama_steward.changes import SCOPES
        s = self.body.get("scope")
        if s in SCOPES:
            return s
        return "until-restart" if (self.evidence or {}).get("finding") else "keep"

    def by(self) -> str:
        return f"{self.peer} via host"

    def os_name(self) -> Optional[str]:
        from halo_harness.ollama_steward.tune_lines import os_of
        return os_of(self.host, self.view.host_card(self.host))

    def publish(self, kind: str, data: dict) -> None:
        from halo_harness.host.jobs import of
        of(self.svc).bus.publish(kind, {**data, "host": self.host.name if self.host else None, "peer": self.peer})

    def forget_card(self) -> None:
        if self.host is not None:
            self.view._cards.pop(self.host.name, None)


HOST = ("str", False, "the Ollama host this host serves (its name; the only one when omitted)")
PORT = ("int", False, "that host's port, instead of its name")
MODEL = ("str", True, "the model")


def table() -> dict:
    from halo_harness.host import ops_control, ops_jobs, ops_manage
    return {op.name: op for op in ops_control.TABLE + ops_jobs.TABLE + ops_manage.TABLE}


def vocabulary() -> list:
    """[{name, grant, params, stated, job, profile, help}] -- `GET me` and docs/HOST.md's table read it."""
    return [{"name": o.name, "grant": o.grant, "params": {k: v[0] + ("" if v[1] else "?") for k, v in o.params.items()},
             "stated": o.stated, "job": o.job, "profile": o.profile, "help": o.help} for o in table().values()]


__all__ = ["Ctx", "HOST", "MODEL", "Op", "PORT", "table", "validate", "vocabulary"]
