"""halo_harness.host.findings -- `GET findings`: the steward's rules over the host's own ledger and events (Halo 3.3.7.0
R2; plans/local-model-fit-brief.md H10.4). No model: rules.gather + run_rules with the host's card and catalog.

Each finding carries `where` and `suggest`:

    where: "host"    a fix the host applies: a profile field (`suggest`: ["set_num_ctx 32768"]) or a server-side
                     line (`suggest`: ["set_kv_cache_type q8_0"], a stated action)
    where: "client"  a fix the harness performs: a prompt that outgrew its window, a reply cut with no room, a
                     compaction that did not run, a switch without fit (`suggest`: ["compact", "a bigger-window
                     model"]); a peer's steward turns it into its own preflight / compact / bigger-window proposal

    host_findings(view) -> [finding + {where, suggest, port}]
    where_of(f) / suggest_of(f)
"""

from __future__ import annotations

CLIENT_RULES = ("no-compaction", "compaction-failed", "cut-resent", "switch-without-fit", "called-wrong", "reply-cut")
FIELD_OPS = {"num_ctx": "set_num_ctx", "num_predict": "set_num_predict", "keep_alive": "set_keep_alive",
             "tools_max": "set_tools_max"}
ENV_OPS = {"OLLAMA_KV_CACHE_TYPE": "set_kv_cache_type", "OLLAMA_FLASH_ATTENTION": "set_flash_attn"}
CLIENT_SUGGEST = ["compact", "a bigger-window model"]


def where_of(f: dict) -> str:
    p = f.get("proposal") or {}
    if f.get("rule") in CLIENT_RULES and p.get("field") not in FIELD_OPS:
        return "client"
    if f.get("rule") == "window-small" and not p:
        return "client"
    if p.get("field") in ("compact_at", "host_for"):
        return "client"
    return "host"


def suggest_of(f: dict) -> list:
    if where_of(f) == "client":
        p = f.get("proposal") or {}
        return ([f"{p['field']} {p['to']}"] if p.get("field") else []) + CLIENT_SUGGEST
    out = []
    p = f.get("proposal") or {}
    if p.get("field") in FIELD_OPS:
        out.append(f"{FIELD_OPS[p['field']]} {p['to']}")
    hint = f.get("server_hint") or {}
    line = str(hint.get("line") or "")
    env = hint.get("env") or next((k for k in ENV_OPS if line.startswith(k + "=")), None)
    if env in ENV_OPS:
        out.append(f"{ENV_OPS[env]} {line.split('=', 1)[1] if '=' in line else ''}".strip())
    elif line:
        out.append(line)
    return out


def host_findings(view) -> list:
    from halo_harness.host.state import port_of
    from halo_harness.ollama_steward.rules import gather, run_rules
    hosts = view.hosts()
    if not hosts:
        return []
    cards = {h.name: view.host_card(h) for h in hosts}
    catalogs = {h.name: {str(r.get("model") or r.get("name")): r for r in view.host_catalog(h)} for h in hosts}
    ctx = gather(view.home, hosts=hosts, cards=cards, catalogs=catalogs)
    ports = {h.name: port_of(h.url) for h in hosts}
    out = []
    for f in run_rules(ctx):
        if f.get("host") not in ports:
            continue
        out.append({**{k: v for k, v in f.items() if k != "plan"}, "where": where_of(f), "suggest": suggest_of(f),
                    "port": ports[f["host"]]})
    return out
