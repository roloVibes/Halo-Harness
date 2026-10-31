"""tests.test_steward_knowledge -- Halo 3.3.4.0 R1: the steward's knowledge
files (`halo_harness/ollama_steward/knowledge/*.md`). Every file is under
250 lines; every claim (a paragraph, a list item, a table row) carries a
`[S<n>]` tag; every tag names a row of SOURCES.md and every row is used;
every row has a URL, a version or commit and a date; no real LAN address;
the symptoms table has a row for every alert kind and parked bug, and its
Halo-side column never answers an outgrown conversation with a smaller
window; the memory file's worked examples match `providers/ollama_fit.py`
(imported and computed here) within each block's stated tolerance; the
directory ships as package data. Files only: no server, no network.
"""
from __future__ import annotations

import os
import re
import sys
import tempfile
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from tests.helpers.runner import Ctx, new_registry, print_results, run_all

os.environ.setdefault("BRIDGE_TEST_HOME", tempfile.mkdtemp(prefix="k1-knowledge-"))
os.environ.setdefault("BRIDGE_TEST_NO_BACKGROUND_NET", "1")

test, TESTS = new_registry()

REPO = Path(__file__).resolve().parent.parent
KDIR = REPO / "halo_harness" / "ollama_steward" / "knowledge"
TOPICS = ("scheduler.md", "log-vocabulary.md", "memory.md", "local-servers.md", "symptoms.md", "server-log.md")  # R3
TAG_RE = re.compile(r"\[S(\d+)\]")
ROW_RE = re.compile(r"^\|\s*S(\d+)\s*\|(.*)\|\s*$")
KINDS = ("prompt-trimmed", "reply-cut", "window-full", "no-user-query", "retry-loop", "http-500",
         "client-gave-up", "load-failed", "cpu-spill", "gpu-memory", "stall", "slow-load", "server-down",
         "compaction-not-firing", "no-reply-reserve", "truncated-reply-resent")
OUTGROWN = ("prompt-trimmed", "reply-cut", "window-full", "no-user-query", "retry-loop", "compaction-not-firing",
            "no-reply-reserve", "truncated-reply-resent")


def _sources() -> "dict[int, list[str]]":
    rows = {}
    for line in (KDIR / "SOURCES.md").read_text(encoding="utf-8").splitlines():
        m = ROW_RE.match(line)
        if m:
            rows[int(m.group(1))] = [c.strip() for c in m.group(2).split("|")]
    return rows


def _claims(text: str) -> "list[str]":
    """The claims of a knowledge file: each paragraph, each list item and
    each table data row; headings, code blocks, table header and divider
    rows and the opening "Read this when" line are not claims."""
    out, block, in_code = [], [], False
    for line in text.splitlines():
        if line.startswith("```"):
            in_code = not in_code
            if block:
                out.append(" ".join(block))
                block = []
            continue
        if in_code:
            continue
        s = line.strip()
        if s.startswith("|"):
            if block:
                out.append(" ".join(block))
                block = []
            if not re.match(r"^\|[\s:|-]+\|$", s):
                out.append(s)
            continue
        if not s or s.startswith("#") or s.startswith("Read this when"):
            if block:
                out.append(" ".join(block))
                block = []
            continue
        if s.startswith("- ") and block:
            out.append(" ".join(block))
            block = []
        block.append(s)
    if block:
        out.append(" ".join(block))
    return out


def _table_headers(text: str) -> "set[str]":
    lines = text.splitlines()
    return {lines[i].strip() for i in range(len(lines) - 1)
            if lines[i].strip().startswith("|") and re.match(r"^\|[\s:|-]+\|$", lines[i + 1].strip())}


@test
def test_every_knowledge_file_is_under_250_lines(ctx: Ctx):
    files = sorted(KDIR.glob("*.md"))
    ctx.check(f"the five topics and SOURCES.md exist: {[f.name for f in files]}",
              {f.name for f in files} >= set(TOPICS) | {"SOURCES.md"})
    for f in files:
        n = f.read_text(encoding="utf-8").count("\n")
        ctx.check(f"{f.name} is under 250 lines ({n})", n < 250)
        ctx.check(f"{f.name} has LF endings", b"\r\n" not in f.read_bytes())


@test
def test_every_claim_ends_in_a_source_tag(ctx: Ctx):
    for name in TOPICS:
        text = (KDIR / name).read_text(encoding="utf-8")
        headers = _table_headers(text)
        bare = [c[:90] for c in _claims(text) if c not in headers and not TAG_RE.search(c)]
        ctx.check(f"{name}: every claim carries a [S<n>] tag; untagged: {bare}", not bare)
        prose = [c for c in _claims(text) if not c.startswith("|")]
        late = [c[:90] for c in prose if not re.search(r"(\[S\d+\])+[.)]?$", c.rstrip())]
        ctx.check(f"{name}: every paragraph and list item ENDS in its tags; not: {late}", not late)


@test
def test_every_tag_names_a_row_and_every_row_is_used(ctx: Ctx):
    rows = _sources()
    ctx.check(f"SOURCES.md has rows S1..S{len(rows)} without gaps", sorted(rows) == list(range(1, len(rows) + 1)))
    used = set()
    for name in TOPICS:
        tags = {int(t) for t in TAG_RE.findall((KDIR / name).read_text(encoding="utf-8"))}
        missing = sorted(tags - set(rows))
        ctx.check(f"{name}: every tag names a SOURCES.md row; unknown: {missing}", not missing)
        used |= tags
    ctx.check(f"every SOURCES.md row is used; unused: {sorted(set(rows) - used)}", not set(rows) - used)


@test
def test_every_source_row_has_a_url_a_version_and_a_date(ctx: Ctx):
    for n, cells in sorted(_sources().items()):
        ctx.check(f"S{n} has four cells: {cells}", len(cells) == 4)
        if len(cells) != 4:
            continue
        title, url, version, read = cells
        ctx.check(f"S{n} has a title", bool(title))
        ctx.check(f"S{n}'s URL is https://, local: or repo: ({url})", re.match(r"^(https://\S+|local:\S.*|repo:\S+)$", url))
        if url.startswith("repo:"):
            ctx.check(f"S{n}'s repo file exists ({url})", (REPO / url[5:]).exists())
        ctx.check(f"S{n} has a version or commit ({version})", len(version) >= 4)
        ctx.check(f"S{n} has a date read ({read})", re.match(r"^\d{4}-\d{2}-\d{2}$", read))


@test
def test_no_real_lan_address_in_the_knowledge(ctx: Ctx):
    from halo_harness.privacy_rules import LAN_IP_RE
    for f in sorted(KDIR.glob("*.md")):
        text = f.read_text(encoding="utf-8")
        found = [m.group(0) for m in LAN_IP_RE.finditer(text)]
        ctx.check(f"{f.name}: no LAN address ({found})", not found)
        ctx.check(f"{f.name}: no real user folder", not re.search(r"C:\\+Users\\+(?!example)", text))


def _symptom_rows() -> "dict[str, list[str]]":
    rows = {}
    for line in (KDIR / "symptoms.md").read_text(encoding="utf-8").splitlines():
        m = re.match(r"^\|\s*`([a-z0-9-]+)`\s*\|(.*)\|\s*$", line)
        if m:
            rows[m.group(1)] = [c.strip() for c in re.split(r"(?<!\\)\|", m.group(2))]
    return rows


@test
def test_the_symptoms_table_has_every_alert_kind(ctx: Ctx):
    rows = _symptom_rows()
    ctx.check(f"a row per alert kind and parked bug; missing: {[k for k in KINDS if k not in rows]}",
              all(k in rows for k in KINDS))
    for kind, cells in rows.items():
        ctx.check(f"{kind}: symptom, cause, Halo-side and server-side cells ({len(cells)})", len(cells) == 4)
        if len(cells) == 4 and kind in OUTGROWN:
            ctx.check(f"{kind}: the Halo side never says a smaller window", "smaller window" not in cells[2].lower())
    spill = rows.get("cpu-spill", ["", "", "", ""])
    ctx.check("cpu-spill: a smaller window is the answer to a spill", "smaller window" in spill[2].lower())


def _examples() -> "list[dict]":
    text = (KDIR / "memory.md").read_text(encoding="utf-8")
    out = []
    for body in re.findall(r"```example\n(.*?)```", text, re.S):
        d = {}
        for line in body.strip().splitlines():
            key, _, value = line.partition(":")
            d[key.strip()] = value.strip()
        out.append(d)
    return out


def _near(a: float, b: float, tol: float) -> bool:
    return abs(a - b) <= tol * max(abs(b), 1.0)


_ATTENTION_KEYS = ("head_count_kv", "key_length", "value_length")


def _model_info(text: str) -> dict:
    """An example's `model_info` line -> `/api/show`-shaped keys (`arch.<key>`;
    the three attention keys under `arch.attention.`)."""
    shape = dict(kv.split("=") for kv in text.split())
    return {(f"arch.attention.{k}" if k in _ATTENTION_KEYS else f"arch.{k}"): int(v) for k, v in shape.items()}


@test
def test_the_worked_examples_match_halos_fit_arithmetic(ctx: Ctx):
    """3.3.4.0 R3: the blocks hold Halo's CORRECTED figures, within 5 % of
    the measured ones (the tolerance line of each block, 0.05; it was 0.01
    while the blocks recorded the old, uncorrected figures)."""
    from halo_harness.providers.ollama_fit import kv_bytes_per_elem_for, kv_bytes_per_token
    from halo_harness.providers.ollama_fit_parts import fit_window, load_parts
    examples = _examples()
    ctx.check(f"the three models rolo runs have a worked example ({len(examples)})",
              {e.get("model") for e in examples} >= {"qwen3-coder:30b", "qwen3.8:27b", "qwen3.5:9b"})
    for e in examples:
        info = _model_info(e["model_info"])
        shape = {k.split(".")[-1]: v for k, v in info.items()}
        bpe = kv_bytes_per_elem_for(e["kv_cache_type"])
        tol = float(e["tolerance"])
        ctx.check(f"{e['model']}: the tolerance is 5 % ({tol})", tol == 0.05)
        halo = kv_bytes_per_token(info, bytes_per_elem=bpe)
        ctx.check(f"{e['model']}: Halo's bytes per token {halo} = the file's {e['halo_kv_bytes_per_token']}",
                  halo is not None and _near(halo, float(e["halo_kv_bytes_per_token"]), tol))
        real = int(e["kv_layers"]) * int(shape["head_count_kv"]) * (int(shape["key_length"]) + int(shape["value_length"])) * bpe
        ctx.check(f"{e['model']}: the arithmetic {real} = the file's {e['real_kv_bytes_per_token']}",
                  _near(real, float(e["real_kv_bytes_per_token"]), tol))
        ctx.check(f"{e['model']}: Halo's figure is the real one now ({halo} vs {real})", _near(halo or 0, real, tol))
        mib = real * int(e["window"]) / 2 ** 20
        ctx.check(f"{e['model']}: {mib} MiB at the window = the file's {e['real_kv_mib']}", _near(mib, float(e["real_kv_mib"]), tol))
        if "measured_total_mib" not in e:
            continue
        proj = int(e["projector_mib"]) * 2 ** 20
        parts = load_parts(info, weight_bytes=int(e["weight_bytes"]), window=int(e["window"]), bytes_per_elem=bpe,
                           projector_bytes=proj)
        total = parts["total"] / 2 ** 20
        ctx.check(f"{e['model']}: Halo's sum {total:.0f} MiB = the measured {e['measured_total_mib']} within 5 %",
                  _near(total, float(e["measured_total_mib"]), tol))
        for key, forced in (("halo_fit", True), ("halo_fit_default", False)):
            fit = fit_window(info, weight_bytes=int(e["weight_bytes"]), free_bytes=int(e["free_bytes"]),
                             bytes_per_elem=bpe, projector_bytes=proj, forced=forced)
            ctx.check(f"{e['model']}: Halo's {key} {fit} = the file's {e[key]}", fit == int(e[key]))


@test
def test_the_knowledge_ships_as_package_data(ctx: Ctx):
    text = (REPO / "pyproject.toml").read_text(encoding="utf-8")
    ctx.check("pyproject's package-data lists ollama_steward/knowledge/*.md", '"ollama_steward/knowledge/*.md"' in text)
    from halo_harness.ollama_steward import knowledge_files
    ctx.check("knowledge_files() finds the seven files (3.3.6.0 R3: server-log.md)", len(knowledge_files()) == 7)


if __name__ == "__main__":
    ctx = Ctx()
    results, passed, failed, skipped = run_all(TESTS, ctx)
    sys.exit(print_results(results, passed, failed, skipped))
