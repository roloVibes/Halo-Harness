"""halo_harness.remote.agent_tail -- the control socket's `agent_tail
{agent_id, n=100, kinds?}` (Halo 3.0.5.0 "Fleet" round R1; split out of
remote/agent_control.py in R4): that agent's last n transcript entries
(agent/agent_transcript.py), a background job's one Bash entry, a finished
sub-agent's from its transcript file. A read: nothing is recorded.
"""

from __future__ import annotations

from pathlib import Path

from halo_harness.agent.agent_transcript import entries_from_nodes, tail
from halo_harness.remote.agent_control import FINISHED, _resolve, _session

TAIL_DEFAULT = 100
TAIL_MAX = 500


def cmd_tail(handle, tree, req: dict) -> dict:
    aid = _resolve(handle, tree, req)
    n = req.get("n", TAIL_DEFAULT)
    n = max(1, min(n if isinstance(n, int) and not isinstance(n, bool) else TAIL_DEFAULT, TAIL_MAX))
    kinds = [k for k in req.get("kinds") if isinstance(k, str)] if isinstance(req.get("kinds"), list) else None
    if aid.startswith("job:"):
        row = next(r for r in tree.public_rows() if r["agent_id"] == aid)
        return {"agent_id": aid, "events": tail([{"kind": "tool_call", "id": aid, "name": "Bash", "ts": row["since"],
                                                  "label": f"Bash: {row.get('task')}", "input": {"command": row["task"]}}],
                                                n, kinds)}
    session = _session(handle, tree, aid)
    from halo_harness.agent.subagent import _agent_log_nodes
    path = (tree.row(aid) or {}).get("transcript")
    nodes = session.log.nodes() if session is not None else (_agent_log_nodes(Path(path)) if path else [])
    final = aid != tree.root_id and tree.state_of(aid) in FINISHED
    return {"agent_id": aid, "events": tail(entries_from_nodes(nodes, final=final), n, kinds)}
