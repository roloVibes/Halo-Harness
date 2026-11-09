"""halo_harness.packs.manifest_services -- a pack's `contributes.services`: programs of the pack the supervisor keeps
running in the background (Halo 3.3.13.0 R3; docs/EXTENSION_API.md "Services", stable in API 1.2).

    contributes:
      services:
        - name: bridge                   # lower-case letters, digits, - and _; the service is <pack id>/<name>
          description: answers the phone # one line: what it does while it runs
          run: ["${halo_python}", "${CLAUDE_PLUGIN_ROOT}/service/run.py"]   # a command in the pack folder, exec form
          autostart: true                # `halo supervise` starts it (false: only Start in the Pack Manager / CLI)
          restart: on-failure            # on-failure (an exit other than 0) | always | never
          health: {file: health.json, max_age_s: 90}   # a file in the pack's data folder it rewrites, or {url: ...}
          log: service.log               # its stdout and stderr, in the pack's data folder

    services_of(manifest)          the entries (mappings only)
    service(manifest, name)        one entry, or None
    key_of(pack_id, name)          "<pack id>/<name>"
    needs(data)                    [("services", "service <name>")] -- the grant every service needs
    health_of(entry)               {"file": rel, "max_age_s": n} | {"url": u} | {}
    log_of(entry)                  the log's path in the data folder ("service-<name>.log" when left out)
    service_lines(data, root)      one line per problem, each naming the entry

The supervisor's side (start, restart by the rule, stop, the state other processes read) is
halo_harness/supervise/services.py; `halo pack test` checks each entry's command and health shape
(packs/test_run_services.py).
"""

from __future__ import annotations

import re
from pathlib import Path

SERVICE_KEYS = ("name", "description", "run", "autostart", "restart", "health", "log")
RESTART = ("on-failure", "always", "never")
HEALTH_KEYS = ("file", "url", "max_age_s")
GRANT = "services"
GRANT_LINE = "runs a program of this pack in the background while the supervisor runs"
NAME = re.compile(r"^[a-z][a-z0-9_]*(-[a-z0-9_]+)*$")
DEFAULT_MAX_AGE_S = 120


def _contributes(manifest) -> dict:
    c = manifest.get("contributes") if isinstance(manifest, dict) else None
    return c if isinstance(c, dict) else {}


def services_of(manifest) -> "list[dict]":
    raw = _contributes(manifest).get("services")
    return [e for e in raw if isinstance(e, dict)] if isinstance(raw, list) else []


def service(manifest, name: str):
    return next((e for e in services_of(manifest) if e.get("name") == name), None)


def key_of(pack_id: str, name: str) -> str:
    return f"{pack_id}/{name}"


def needs(data) -> "list[tuple[str, str]]":
    return [(GRANT, f"service {e.get('name')}") for e in services_of(data) if isinstance(e.get("name"), str)]


def restart_of(entry: dict) -> str:
    r = entry.get("restart")
    return r if r in RESTART else "on-failure"


def health_of(entry: dict) -> dict:
    h = entry.get("health") if isinstance(entry.get("health"), dict) else {}
    if isinstance(h.get("file"), str) and h["file"].strip():
        age = h.get("max_age_s")
        ok = isinstance(age, (int, float)) and not isinstance(age, bool) and age > 0
        return {"file": h["file"].strip(), "max_age_s": float(age) if ok else float(DEFAULT_MAX_AGE_S)}
    if isinstance(h.get("url"), str) and h["url"].strip():
        return {"url": h["url"].strip()}
    return {}


def log_of(entry: dict) -> str:
    log = entry.get("log")
    if isinstance(log, str) and log.strip():
        return log.strip().replace("\\", "/")
    return f"service-{entry.get('name') or 'main'}.log"


def _rel_problem(rel: str) -> str:
    p = Path(rel.replace("\\", "/"))
    if p.is_absolute() or rel.startswith(("/", "\\")) or re.match(r"^[A-Za-z]:", rel) or ".." in p.parts or "$" in rel:
        return f"{rel!r} is outside the pack's data folder (a path inside it: health.json, logs/service.log)"
    return ""


def _health_lines(where: str, h) -> "list[str]":
    if h is None:
        return []
    if not isinstance(h, dict):
        return [f"{where}.health: a mapping, {{file: <name>, max_age_s: <n>}} or {{url: http://127.0.0.1:<port>/...}}"]
    out = [f"{where}.health.{k}: not a key (file, url, max_age_s)" for k in h if k not in HEALTH_KEYS]
    has_file, has_url = isinstance(h.get("file"), str) and h["file"].strip(), isinstance(h.get("url"), str) and h["url"].strip()
    if bool(has_file) == bool(has_url):
        out.append(f"{where}.health: exactly one of file (a file it rewrites) or url (an address that answers 200)")
    if has_file:
        line = _rel_problem(h["file"].strip())
        out += [f"{where}.health.file: {line}"] if line else []
    if has_url and not re.match(r"^https?://(127\.0\.0\.1|localhost|\[::1\])(:\d+)?(/|$)", h["url"].strip()):
        out.append(f"{where}.health.url: {h['url']!r} -- a health url is on this machine (http://127.0.0.1:<port>/...)")
    age = h.get("max_age_s")
    if age is not None and (not isinstance(age, (int, float)) or isinstance(age, bool) or age <= 0):
        out.append(f"{where}.health.max_age_s: {age!r} is not a number of seconds above 0")
    return out


def service_lines(data, root=None) -> "list[str]":
    raw = _contributes(data).get("services")
    if raw is None:
        return []
    if not isinstance(raw, list):
        return ["contributes.services: a list of {name, run, autostart, restart, health, log}"]
    from halo_harness.packs.manifest_policy import script_rel
    out: "list[str]" = []
    seen: set = set()
    for i, e in enumerate(raw):
        where = f"contributes.services[{i}]"
        if not isinstance(e, dict):
            out.append(f"{where}: a mapping {{name, run, ...}}")
            continue
        name = e.get("name")
        if isinstance(name, str) and name:
            where = f"contributes.services[{name}]"
        if not isinstance(name, str) or not NAME.match(name):
            out.append(f"{where}.name: {name!r} is not a name (lower-case letters, digits, - and _)")
        elif name in seen:
            out.append(f"{where}.name: {name!r} is used twice")
        seen.add(name)
        out += [f"{where}.{k}: not a key ({', '.join(SERVICE_KEYS)})" for k in e if k not in SERVICE_KEYS]
        rel, why = script_rel(e.get("run"))
        if why:
            out.append(f"{where}.run: {why}")
        elif root is not None and not (Path(root) / rel).is_file():
            out.append(f"{where}.run: {rel} is not in the pack")
        if e.get("autostart") is not None and not isinstance(e.get("autostart"), bool):
            out.append(f"{where}.autostart: true or false")
        if e.get("restart") is not None and e.get("restart") not in RESTART:
            out.append(f"{where}.restart: {e.get('restart')!r} is not one of {', '.join(RESTART)}")
        out += _health_lines(where, e.get("health"))
        if e.get("log") is not None:
            log = e.get("log")
            line = _rel_problem(log) if isinstance(log, str) and log.strip() else "a file name in the pack's data folder"
            out += [f"{where}.log: {line}"] if line else []
        if e.get("description") is not None and not (isinstance(e["description"], str) and e["description"].strip()):
            out.append(f"{where}.description: one line, what it does while it runs")
    return out
