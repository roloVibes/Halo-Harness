"""tests.helpers.fake_postiz -- a fake `postiz` executable (Halo 3.0.4.0 R4).

    install(dir, log, **options) -> dir      writes `postiz` (a shell script on POSIX,
                                             `postiz.cmd` on Windows) + its program
    put_on_path(dir)                         a context manager: dir first on PATH
    calls(log) -> [{"argv": [...], "has_key": bool}]

The program answers integrations:list, upload, posts:create, posts:status,
analytics:post and analytics:platform with canned JSON and appends one line
per call (the argv and whether POSTIZ_API_KEY was in its env -- never the
key) to `log`. Options: `integrations` (a list of {id, identifier, name,
disabled}), `table` (print integrations:list as a column table),
`fail_upload` (upload exits 1 with a stderr message), `fail_create_for` (a
list of integration ids whose posts:create exits 1 echoing the key to
stderr), `fail_analytics`, `banner` (print a log line before the JSON).
"""

from __future__ import annotations

import contextlib
import json
import os
import stat
import sys
from pathlib import Path

INTEGRATIONS = [
    {"id": "int-yt", "identifier": "youtube", "name": "Halo Channel", "disabled": False},
    {"id": "int-ig", "identifier": "instagram", "name": "halo.ig", "disabled": False},
    {"id": "int-x", "identifier": "x", "name": "@halo", "disabled": False},
    {"id": "int-tt", "identifier": "tiktok", "name": "halo.tt", "disabled": False},
]

PROGRAM = r'''
import json, os, re, sys
here = os.path.dirname(os.path.abspath(__file__))
cfg = json.load(open(os.path.join(here, "config.json"), encoding="utf-8"))
argv = sys.argv[1:]
with open(cfg["log"], "a", encoding="utf-8") as fh:
    fh.write(json.dumps({"argv": argv, "has_key": bool(os.environ.get("POSTIZ_API_KEY"))}) + "\n")
if cfg.get("banner"):
    print("[postiz] using https://api.postiz.example")
cmd = argv[0] if argv else ""


def opt(flag):
    return argv[argv.index(flag) + 1] if flag in argv else ""


def counter(name):
    path = os.path.join(here, name + ".count")
    n = int(open(path).read()) + 1 if os.path.exists(path) else 1
    open(path, "w").write(str(n))
    return n


if cmd == "integrations:list":
    rows = cfg["integrations"]
    if cfg.get("table"):
        print("ID        Platform    Name            Disabled")
        print("--------  ----------  --------------  --------")
        for r in rows:
            print("%-8s  %-10s  %-14s  %s" % (r["id"], r["identifier"], r["name"], "yes" if r.get("disabled") else "no"))
    else:
        print(json.dumps(rows))
elif cmd == "upload":
    if cfg.get("fail_upload"):
        sys.stderr.write("error: upload failed: 413 payload too large\n")
        sys.exit(1)
    n = counter("upload")
    print(json.dumps({"id": "up-%d" % n, "path": "https://postiz.example/uploads/" + os.path.basename(argv[1])}))
elif cmd == "posts:create":
    if opt("-i") in cfg.get("fail_create_for", []):
        sys.stderr.write("error: create failed for %s (key %s)\n" % (opt("-i"), os.environ.get("POSTIZ_API_KEY", "")))
        sys.exit(1)
    n = counter("post")
    print(json.dumps([{"postId": "post-%d" % n, "integration": opt("-i")}]))
elif cmd == "posts:status":
    print(json.dumps({"id": argv[1], "status": "QUEUE"}))
elif cmd == "analytics:post":
    if cfg.get("fail_analytics"):
        sys.stderr.write("error: analytics unavailable\n")
        sys.exit(1)
    k = int(re.sub(r"\D", "", argv[1]) or 1)
    days = int(opt("-d") or 7)
    series = lambda label, v: {"label": label, "data": [{"total": str(v // 2), "date": "d1"}, {"total": str(v), "date": "d2"}],
                               "percentageChange": 5}
    print(json.dumps([series("Views", 100 * k), series("Likes", 10 * k), series("Comments", 2 * k),
                      series("Shares", k), series("Days", days)]))
elif cmd == "analytics:platform":
    print(json.dumps([{"label": "Followers", "data": [{"total": "1234", "date": "d1"}], "percentageChange": 1}]))
else:
    sys.stderr.write("error: unknown command %r\n" % cmd)
    sys.exit(2)
'''


def install(dir, log, **options) -> Path:
    d = Path(dir)
    d.mkdir(parents=True, exist_ok=True)
    cfg = {"log": str(log), "integrations": INTEGRATIONS, **options}
    (d / "config.json").write_text(json.dumps(cfg), encoding="utf-8")
    (d / "fake_postiz_main.py").write_text(PROGRAM, encoding="utf-8")
    Path(log).touch()
    main = d / "fake_postiz_main.py"
    if os.name == "nt":
        (d / "postiz.cmd").write_text(f'@"{sys.executable}" "{main}" %*\r\n', encoding="utf-8")
    else:
        shim = d / "postiz"
        shim.write_text(f'#!/bin/sh\nexec "{sys.executable}" "{main}" "$@"\n', encoding="utf-8")
        shim.chmod(shim.stat().st_mode | stat.S_IXUSR | stat.S_IXGRP | stat.S_IXOTH)
    return d


def calls(log) -> list:
    p = Path(log)
    return [json.loads(l) for l in p.read_text(encoding="utf-8").splitlines() if l.strip()] if p.is_file() else []


@contextlib.contextmanager
def put_on_path(dir, key: "str | None" = None, exclusive: bool = False, **env):
    """`dir` first on PATH (the only entry when `exclusive`), POSTIZ_API_KEY=key when given, for the block;
    everything restored after."""
    names = ["PATH", "POSTIZ_API_KEY", "POSTIZ_API_URL", *env]
    saved = {n: os.environ.get(n) for n in names}
    os.environ["PATH"] = str(dir) + ("" if exclusive else os.pathsep + (saved["PATH"] or ""))
    os.environ.pop("POSTIZ_API_KEY", None)
    os.environ.pop("POSTIZ_API_URL", None)
    if key:
        os.environ["POSTIZ_API_KEY"] = key
    os.environ.update(env)
    try:
        yield
    finally:
        for n, v in saved.items():
            if v is None:
                os.environ.pop(n, None)
            else:
                os.environ[n] = v
