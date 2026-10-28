"""halo_harness.commands.ollama_slash -- `/ollama` (Halo 3.3.4.0 R5): the Ollama steward in the prompt, the
text Studio's Ollama panel shows (studio/ollama_hosts_view.py reads the same functions and shares its 60 s
card cache).

    /ollama [--host NAME]                 per host the card line, the last hour's rollups (`halo ollama traffic
                                          --since 1h`), the profiles; the Hugging Face local servers' lines; the
                                          job's status line, the last note (and the hub's on a member), the
                                          review-mode proposals with their `halo ollama steward apply <id>`
    /ollama findings [--host NAME]        `halo ollama steward findings`
    /ollama plan [--host NAME]            `halo ollama steward plan`
    /ollama explain [<kind> | <topic>]    `halo ollama explain`, from the knowledge, no model
    /ollama hosts [--host NAME] [--refresh]   the per-host analysis (2.0.3 round 3; the TUI's dialog)

Never a model call and never a write to a server.
"""

from __future__ import annotations

SUBS = ("findings", "plan", "explain", "hosts")
MORE = "more: /ollama findings | plan | explain <kind> | hosts; in Studio: Fleet, the Ollama panel"


def _state():
    from halo_harness.config.paths import bridge_home
    return bridge_home()


def _host_arg(tokens: list) -> "tuple[str, list]":
    if "--host" in tokens:
        i = tokens.index("--host")
        name = tokens[i + 1] if i + 1 < len(tokens) else ""
        return name, tokens[:i] + tokens[i + 2:]
    return "", tokens


def _card_line(host) -> str:
    from halo_harness.ollama_steward.hardware import format_card
    from halo_harness.studio.ollama_hosts_view import card_of
    card = card_of(host)
    keep = [x for x in (format_card(card) if card else []) if x.startswith(("GPU ", "server ", "memory: ", "other: "))]
    return "; ".join(keep) or "card not read"


def _steward_lines(state) -> list:
    from halo_harness.ollama_steward import job_state, notes, steward
    from halo_harness.ollama_steward.agent import choose_model
    st = job_state.status(state)
    if not st.get("running"):
        st["model"], st["model_why"] = choose_model(state_dir=state)
    last = notes.latest(state, stages=("note",)) or notes.latest(state, stages=("change", "finding"))
    out = [f"Ollama steward (mode {steward.mode()})"] + job_state.format_status(st)
    if last:
        lines = last.get("lines") or [last.get("say") or ""]
        out.append(f"last note {last.get('at')}: {lines[0]}")
        out.extend(f"  {x}" for x in lines[1:])
    else:
        out.append("last note: none yet (the steward writes one when its rules find something new)")
    hub = notes.member_line(notes.hub_note(state))
    if hub:
        out.append(hub)
    return out


def _proposals(state) -> list:
    from halo_harness.ollama_steward import steward
    journal = steward.read_journal(state)
    quiet = steward.dismissed(state, journal=journal)
    applied = {r.get("finding") for r in journal if r.get("kind") == "apply"}
    rows = [r for r in journal if r.get("kind") == "proposal" and r.get("id") not in quiet | applied]
    if not rows:
        return []
    return ["proposals (review mode):"] + [f"  [{r['id']}] {r.get('field')} {r.get('from')} -> {r.get('to')} for "
                                           f"{r.get('key')} ({r.get('why')}); halo ollama steward apply {r['id']}"
                                           for r in rows[-10:]]


def overview(host_name: str = "") -> str:
    from halo_harness.ollama_steward.ledger import read_calls
    from halo_harness.ollama_steward.profiles import all_profiles, split_key
    from halo_harness.ollama_steward.traffic import format_row, rollup
    from halo_harness.providers.ollama import resolve_ollama_hosts
    from halo_harness.studio.ollama_hosts_view import _base, local_servers
    state = _state()
    hosts = [h for h in resolve_ollama_hosts() if not host_name or h.name.lower() == host_name.lower()]
    if host_name and not hosts:
        return f"/ollama: no configured host named {host_name!r} (see ollama.hosts)"
    hour = read_calls(state, since=3600.0)
    rows = rollup(hour, resolve_ollama_hosts())
    profiles = all_profiles()
    out = _steward_lines(state)
    for h in hosts:
        out += ["", f"'{h.name}' ({h.url}): {_card_line(h)}"]
        mine = [r for r in rows if r["host"] == h.name]
        out += ["  the last hour:"] + [f"  {format_row(r)}" for r in mine] if mine else ["  no calls in the last hour"]
        prof = [(k, v) for k, v in profiles.items() if split_key(k)[0] == h.name]
        for k, v in prof:
            fields = ", ".join(f"{f} {v[f]}" for f in ("num_ctx", "num_predict", "keep_alive", "tools_max", "host_for",
                                                         "compact_at") if f in v)
            out.append(f"  profile {split_key(k)[1]}: {fields} (by {v.get('by') or 'you'})")
    for s in ([] if host_name else local_servers()):
        mine = [{**x, "host": {"name": s.name, "url": s.url}} for x in hour if x.get("dialect") == "openai"
                and _base((x.get("host") or {}).get("url")) == _base(s.url)]
        out += ["", f"local server '{s.name}' ({s.url}): the window and reply rules apply"]
        out += [f"  {format_row(r)}" for r in rollup(mine, [])] if mine else ["  no calls in the last hour"]
    if not host_name:
        out.append("Hugging Face beyond the local servers: next, the Models section (3.3.5.0)")
    out += [""] + (_proposals(state) or []) + [MORE]
    return "\n".join(out).replace("\n\n\n", "\n\n")


def findings_text(host_name: str = "") -> str:
    from halo_harness.ollama_steward.rules import findings, format_finding
    from halo_harness.studio.ollama_hosts_view import readers
    found = findings(_state(), since="24h", host=host_name or None, **readers())
    if not found:
        return "no findings in the last 24h: the calls in the ledger and the server's lines look right"
    return "\n".join("\n".join(format_finding(f)) for f in found)


def plan_text(host_name: str = "") -> str:
    from halo_harness.ollama_steward.fit import format_plan, plan
    from halo_harness.ollama_steward.rules import gather
    from halo_harness.ollama_steward.rules_host import _asked, _serving
    from halo_harness.studio.ollama_hosts_view import readers
    ctx = gather(_state(), since="24h", host=host_name or None, **readers())
    by_host: dict = {}
    for g in ctx["groups"]:
        by_host.setdefault(g["host"], []).append(g)
    plans = [plan(ctx["cards"].get(h) or {}, [_asked(g) for g in gs], ctx["catalogs"].get(h) or {}, host_name=h,
                  other_hosts=lambda m, h=h: _serving(ctx, m, h)) for h, gs in by_host.items()]
    return "\n".join("\n".join(format_plan(p)) for p in plans) or "nothing to plan: no calls in the ledger's window"


def ollama_text(args: str) -> str:
    """`/ollama ...` without the `hosts` dialog (the TUI opens that itself)."""
    tokens = (args or "").split()
    sub = tokens[0].lower() if tokens and tokens[0].lower() in SUBS else ""
    rest = tokens[1:] if sub else tokens
    if sub == "explain":
        from halo_harness.ollama_steward.explain import explain
        lines, _ok = explain(" ".join(rest) or None)
        return "\n".join(lines)
    host, rest = _host_arg(rest)
    if sub == "findings":
        return findings_text(host)
    if sub == "plan":
        return plan_text(host)
    if rest and not host:
        return f"/ollama: unknown argument {' '.join(rest)!r} ({MORE})"
    return overview(host)
