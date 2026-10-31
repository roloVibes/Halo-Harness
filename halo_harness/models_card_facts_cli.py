"""halo_harness.models_card_facts_cli -- Halo 3.3.6.0 R4: two of the card's
facts from the terminal (catalog_cli.cmd_models dispatches the verbs):

    halo models measured <model> [--host H] [--json]
        the Measured block alone (providers/measured.py): each fact "value (source, date, n)"
    halo models dialect <model> [--host H] [--set field=value ...] [--reset [FIELD]] [--json]
        the dialect record (providers/dialect.py): each field, its value and where it came from;
        --set writes your edit (marked `user`: it wins over the battery and the ledger),
        --reset puts one field, or every field, back to what the battery says

`<model>` is an Ollama name or an `ol:<model>@<host>` ref; the host is the default
one unless `--host` or the ref names it. Nothing here sends a request.
"""

from __future__ import annotations

import argparse
import json
import sys


def _target(model: str, host_name):
    from halo_harness.providers.ollama import resolve_ollama_host
    m = model[3:] if model.startswith("ol:") else model
    name, at, h = m.rpartition("@")
    if at and name:
        m, host_name = name, host_name or h
    host = resolve_ollama_host(host_name or None)
    return m, getattr(host, "name", None)


def cmd_models_measured(argv: list) -> int:
    from halo_harness.config.paths import bridge_home
    from halo_harness.providers.measured import lines, measured_for
    p = argparse.ArgumentParser(prog="halo models measured", description="What this model measured on this host: "
                                "tok/s, first token, load, cache reuse, the window, KV per token, modality, "
                                "speculative decoding, tool-call accuracy, quirks -- each with its source, date and n.")
    p.add_argument("model")
    p.add_argument("--host", default=None)
    p.add_argument("--json", action="store_true")
    a = p.parse_args(argv)
    model, host = _target(a.model, a.host)
    if not host:
        print(f"halo models measured: no Ollama host named {a.host!r}", file=sys.stderr)
        return 1
    m = measured_for(host, model, state_dir=bridge_home())
    if a.json:
        print(json.dumps(m, indent=2, default=str))
        return 0
    got = lines(m)
    print(f"{model} on {host}: measured over its last {m.get('n_calls', 0)} answered calls (never the first after a load)")
    for line in got or ["nothing measured yet: run a session on it, or halo models probe " + model]:
        print(f"  {line}")
    return 0


def _sets(pairs: list) -> "tuple[dict, list]":
    from halo_harness.providers.dialect import FIELDS, parse
    out, bad = {}, []
    for pair in pairs or []:
        field, eq, value = pair.partition("=")
        field = field.strip().replace("-", "_")
        if not eq or field not in FIELDS:
            bad.append(f"{pair!r}: field=value, a field of {', '.join(FIELDS)}")
            continue
        try:
            out[field] = parse(field, value)
        except ValueError:
            bad.append(f"{pair!r}: {value!r} is not a value for {field}")
    return out, bad


def cmd_models_dialect(argv: list) -> int:
    from halo_harness.config.paths import bridge_home
    from halo_harness.providers.dialect import record, reset, set_fields, view
    p = argparse.ArgumentParser(prog="halo models dialect", description="How Halo talks to this model on this host: "
                                "instruction placement, fence stripping, the reply reserve, the JSON repair loop, "
                                "stop tokens, the loop guard, thinking, the tool budget.")
    p.add_argument("model")
    p.add_argument("--host", default=None)
    p.add_argument("--set", dest="sets", action="append", default=[], metavar="FIELD=VALUE")
    p.add_argument("--reset", nargs="?", const="", default=None, metavar="FIELD")
    p.add_argument("--json", action="store_true")
    a = p.parse_args(argv)
    model, host = _target(a.model, a.host)
    if not host:
        print(f"halo models dialect: no Ollama host named {a.host!r}", file=sys.stderr)
        return 1
    if a.reset is not None:
        reset(host, model, a.reset or None)
        print(f"{model} on {host}: {a.reset or 'every field'} back to what the battery says")
    if a.sets:
        changes, bad = _sets(a.sets)
        if not bad:
            _stored, bad = set_fields(host, model, changes, by="user")
        if bad:
            for line in bad:
                print(f"halo models dialect: {line}", file=sys.stderr)
            return 2
        print(f"{model} on {host}: {', '.join(changes)} set (yours: the battery and the ledger never change it)")
    rec = record(host, model, state_dir=bridge_home())
    if a.json:
        print(json.dumps(rec, indent=2, default=str))
        return 0
    print(f"how Halo talks to {model} on {host}:")
    for line in view(rec)["lines"]:
        print(f"  {line}")
    print(f"  change one: halo models dialect {model} --host {host} --set reply_reserve=2048")
    return 0
