r"""tests.test_privacy_redact -- Halo 3.4.1.2 (PACKS-5, SERVERS-6): the replay scrub and the export redactor missed
common spellings of the home path, the user and machine names and several key shapes. Now one function
(halo_harness/privacy_redact.redact) serves a saved replay, `halo export --sanitize`, `/export --sanitize`,
`halo session export`, the report card's Markdown and the bug report, and:

1. every spelling in both findings is caught: a word character before the drive letter, URL-encoded paths, `..`
   paths, the machine name in a URL, the user name in a URL path and in `user@host:`, 8.3 short names, `gsk_` /
   `xai-` / `pplx-` keys, a bare JWT, the launch token in `#t=` and a pack key in `?k=`, a bare 30-character token,
   the value of a secret environment variable (raw and percent-encoded), the ID keys `to` / `agent_id` / `parent`, the
   `plan` subtree and dict keys;
2. the four outputs all go through it;
3. a seeded generator (case, separators, percent / double encoding, JSON escaping, full-width look-alikes, prefixes
   and suffixes, every kind of field) never gets one of the secrets through. Kept as a test: change a rule and it runs
   again. Out of reach by design, and said in the hand-back: a name split across two fields, and look-alikes that NFKC
   does not fold (Cyrillic / Greek letters).
Run: python -m tests.test_privacy_redact
"""
from __future__ import annotations

import json
import os
import random
import sys
import unicodedata
from pathlib import Path
from urllib.parse import quote, unquote

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from tests.helpers.runner import Ctx, new_registry, print_results, run_all  # noqa: E402

test, TESTS = new_registry()
USER, MACHINE = "jsmithersen", "DESKTOP-JS42"
HOME = "C:\\Users\\" + USER
NIX = "/home/" + USER
ENV_SECRET = "Zq9-swordfish-Kx7-ENVVALUE-41"
TOKENS = {"gsk": "gsk_" + "Ab3" * 12, "xai": "xai-" + "Q7w" * 12, "pplx": "pplx-" + "Lm4" * 12,
          "jwt": "eyJhbGciOiJIUzI1NiJ9.eyJzdWIiOiJqc21pdGgifQ.c2lnbmF0dXJlLWZha2UtMTIz",
          "bare": "aB3dE5fG7hJ9kL1mN3pQ5rS7tU9vW1xY", "launch": "Tk4-q9ZrXy27_LmNoPq3RsTuVw5XyZa1bC"}
NAMES = dict(homes=[HOME, NIX], users=[USER], machines=[MACHINE])


def _redact(obj, **kw):
    from halo_harness.privacy_redact import redact
    old = os.environ.get("HALO_TEST_SERVICE_TOKEN")
    os.environ["HALO_TEST_SERVICE_TOKEN"] = ENV_SECRET
    try:
        return redact(obj, **{**NAMES, **kw})
    finally:
        os.environ.pop("HALO_TEST_SERVICE_TOKEN", None) if old is None else os.environ.__setitem__(
            "HALO_TEST_SERVICE_TOKEN", old)


def _readable(obj) -> str:
    """What a reader of the output sees, every encoding undone and look-alikes folded, in lower case."""
    text = json.dumps(obj, ensure_ascii=False)
    text = json.loads(json.dumps(text))  # the JSON escapes as characters
    for _ in range(4):
        text = unquote(text)
    return unicodedata.normalize("NFKC", text.replace("\\\\", "\\")).lower()


def _leaks(obj) -> list:
    seen = _readable(obj)
    secrets = [USER, MACHINE, ENV_SECRET, *TOKENS.values()]
    return [s for s in secrets if s.lower() in seen]


@test
def test_packs5_servers6_every_spelling_in_the_findings(ctx: Ctx):
    lines = {
        "word_before_drive": "x_" + HOME + "\\.ssh\\id_rsa",
        "url_encoded_file": "file:///C%3A/Users/" + USER + "/notes.txt",
        "url_encoded_both": "C%3A%5CUsers%5C" + USER + "%5Cx",
        "dotdot": "..\\..\\Users\\" + USER + "\\.ssh\\id_rsa",
        "machine_in_url": "http://" + MACHINE + ":8765/api",
        "user_in_url_path": "https://example.com/u/" + USER + "/x",
        "short_name": "C:\\Users\\JSMITH~1\\AppData\\Local\\Temp\\a.txt",
        "user_at_host": "ssh " + USER + "@" + MACHINE + ":/srv/x then open http://" + MACHINE + ":8188/view",
        "launch": "http://127.0.0.1:8765/?mode=session#t=" + TOKENS["launch"],
        "pack_key": "http://127.0.0.1:8765/api/packs/design/raw/a.png?k=" + TOKENS["launch"],
        "env_raw": "the service said " + ENV_SECRET, "env_encoded": "q=" + quote(ENV_SECRET, safe=""),
        **{k: f"key {v} here" for k, v in TOKENS.items() if k not in ("launch",)},
    }
    payload = {"title": "t", "marks": [{"text": v, "what": k} for k, v in lines.items()],
               "agents": [{"agent_id": USER + "-coder", "to": "main", "parent": MACHINE}],
               "plan": {"blocks": [{"name": "files of " + USER, "path": NIX + "/proj"}]},
               "agent_costs": {USER: 1.0}}
    got = _redact(payload)
    for m in got["marks"]:
        ctx.check(f"{m['what']}: nothing leaks, got {m['text']!r}", not _leaks(m["text"]))
    ctx.check(f"agent_id / parent are scrubbed, got {got['agents']}", not _leaks(got["agents"]))
    ctx.check(f"the plan subtree is scrubbed, got {got['plan']}", not _leaks(got["plan"]))
    ctx.check(f"dict keys are scrubbed, got {list(got['agent_costs'])}", not _leaks(list(got["agent_costs"])))
    root = HOME + "\\proj"
    ctx.check("a path the root rule made project-relative keeps its words; one the model wrote does not",
              _redact({"t": "see " + root + "\\src\\" + USER + "\\notes.md"}, root=root)["t"]
              == "see src/" + USER + "/notes.md"
              and not _leaks(_redact({"t": "see src/" + USER + "/notes.md"}, root=root)))


@test
def test_packs5_the_four_outputs_use_the_one_function(ctx: Ctx):
    text = f"read {HOME}\\a.txt on {MACHINE} with {TOKENS['gsk']} and {ENV_SECRET}"
    from halo_harness.live.report_card_text import markdown
    from halo_harness.redact import redact_for_bugreport
    from halo_harness.session_trace import _scrub
    from halo_harness.controller import sanitize_transcript
    keys = ("HALO_TEST_SERVICE_TOKEN", "USERPROFILE", "COMPUTERNAME", "USERNAME")
    saved = {k: os.environ.get(k) for k in keys}  # every one put back: Path.home() reads USERPROFILE
    os.environ.update(HALO_TEST_SERVICE_TOKEN=ENV_SECRET, USERPROFILE=HOME, COMPUTERNAME=MACHINE, USERNAME=USER)
    try:
        outs = {"bug report": redact_for_bugreport(text), "session export": _scrub(text),
                "report card": markdown({"title": "t", "cells": {}, "story": [{"at": "0:01", "text": text}]}),
                "/export --sanitize": sanitize_transcript(text)}
    finally:
        for k, v in saved.items():
            os.environ.pop(k, None) if v is None else os.environ.__setitem__(k, v)
    for name, out in outs.items():
        ctx.check(f"{name}: no key, path, user or machine, got {out[-200:]!r}", not _leaks(out))
    src = (Path(__file__).resolve().parent.parent / "halo_harness" / "export_cli.py").read_text(encoding="utf-8")
    ctx.check("halo export --sanitize calls privacy_redact.redact", "privacy_redact import redact" in src)


def _variants(rng: random.Random, value: str, case: bool = True) -> list:
    """`case`: names and paths change case and stay what they are; a key in another case is no longer the key."""
    full = lambda s: "".join(chr(ord(c) + 0xFEE0) if "!" <= c <= "~" else c for c in s)  # noqa: E731 -- full-width
    out = [value, quote(value, safe=""), quote(quote(value, safe=""), safe=""), full(value)]
    if case:
        out += [value.upper(), value.lower(), "".join(c.upper() if rng.random() < .5 else c.lower() for c in value)]
    if "\\" in value:
        out += [value.replace("\\", "/"), value.replace("\\", "\\\\"), value.replace("\\", "/").replace("/", "//", 1),
                value.replace("\\", rng.choice(["/", "\\"])), quote(value, safe=":")]
    return out


PREFIX = ["", "x_", "see ", "(", "'", "\"", "=", "@", "http://", "file:///", "..\\..\\", "path=", "<", "a:", "\t",
          "%20", "{\"p\": \"", "`", "[", "-", "1", "user:", "ssh://"]
SUFFIX = ["", ".", ",", ")", ":8080/x", "/sub/file.txt", "\\file.txt", "_notes", "-2", "'", "\n", "\"}", "`", "]",
          "%2Fx", ";", "@host", "?a=b", "#frag"]


@test
def test_packs5_generator_finds_no_leak(ctx: Ctx):
    rng = random.Random(3412)
    seeds = [USER, MACHINE, HOME, HOME + "\\.ssh\\id_rsa", NIX + "/x", ENV_SECRET, *TOKENS.values(),
             "C:\\Users\\JSMITH~1\\x", USER + "@" + MACHINE, "\\\\?\\" + HOME + "\\x", "/mnt/c/Users/" + USER + "/x",
             "/c/Users/" + USER + "/x", USER + "_" + MACHINE, "\\\\" + MACHINE + "\\share\\" + USER]
    leaked, n = [], 0
    for seed in seeds:
        for v in _variants(rng, seed, case=seed not in TOKENS.values() and seed != ENV_SECRET):
            for _ in range(10):
                s = rng.choice(PREFIX) + v + rng.choice(SUFFIX)
                s = json.dumps({"inner": s}) if rng.random() < .15 else s  # a JSON text inside a string
                where = rng.choice(["text", "to", "agent_id", "parent", "plan", "key", "nested"])
                payload = {"title": "t", "text": s} if where == "text" else \
                    {"agents": [{where: s}]} if where in ("to", "agent_id", "parent") else \
                    {"plan": {"blocks": [{"name": s}]}} if where == "plan" else \
                    {"costs": {s: 1}} if where == "key" else {"marks": [{"a": [{"b": s}]}]}
                n += 1
                got = _leaks(_redact(payload))
                if got:
                    leaked.append((where, s, got))
    ctx.check(f"{n} generated payloads, no leak; first ones: {leaked[:5]}", not leaked and n > 500)


if __name__ == "__main__":
    ctx = Ctx()
    results, passed, failed, skipped = run_all(TESTS, ctx)
    sys.exit(print_results(results, passed, failed, skipped))
