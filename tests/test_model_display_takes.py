"""tests.test_model_display_takes -- the picker says what a model takes (Halo
3.3.15.0 R2): `model_takes.takes_words` reads only what a catalog row states
(text always, vision / audio / video / pdf in, image out, tools and think when
stated or measured, `?` when no input list is stated); the terminal picker's
row puts `takes=` right after the ref and the prices before ctx and speed, so
a narrow terminal cuts ctx and speed first; `/model <ref>`'s confirmation
suffix reads the best-at cache; `halo models` prints a takes column (`?`
when not stated) with the prices still blank-when-unpublished; `halo models
show` prints the honest line; Studio's model rows, the Setup rows and the
new-session rows carry `takes`.
Run: python -m tests.test_model_display_takes
"""
from __future__ import annotations

import io
import json
import os
import sys
import tempfile
from contextlib import redirect_stdout
from pathlib import Path
from types import SimpleNamespace

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from tests.helpers.provider_env_defaults import ensure_scoped_state_dir_once

ensure_scoped_state_dir_once()

from tests.helpers.runner import Ctx, new_registry, print_results, run_all  # noqa: E402

test, TESTS = new_registry()

EYES = {"ref": "or:v/eyes", "provider": "openrouter", "modalities_in": ["text", "image", "file"], "tools": True,
        "reasoning": {"kind": "native", "efforts": []}, "price_in_per_m": 3.0, "price_out_per_m": 15.0,
        "context_tokens": 1_000_000, "speed_ttft_s": 0.9, "speed_tokens_per_second": 55}
PLAIN = {"ref": "or:v/plain", "provider": "openrouter", "modalities_in": ["text"], "price_in_per_m": 0.1, "price_out_per_m": 0.4}
BLANK = {"ref": "dbx:some-endpoint", "provider": "databricks"}
_KEYS = ("BRIDGE_TEST_HOME", "BRIDGE_STATE_DIR", "BRIDGE_ENV_FILE", "OPENROUTER_API_KEY", "OPENROUTER_BASE_URL")


class _Env:
    def __enter__(self):
        self._saved = {k: os.environ.get(k) for k in _KEYS}
        d = Path(tempfile.mkdtemp(prefix="r3315-takes-"))
        os.environ["BRIDGE_TEST_HOME"] = str(d)
        os.environ["BRIDGE_STATE_DIR"] = str(d / ".halo")
        os.environ["BRIDGE_ENV_FILE"] = str(d / "no-env-file")
        os.environ["OPENROUTER_API_KEY"] = "sk-or-fake"
        os.environ["OPENROUTER_BASE_URL"] = "http://127.0.0.1:9/api/v1"
        self.home, self.state_dir = d, d / ".halo"
        self.state_dir.mkdir(parents=True, exist_ok=True)
        return self

    def __exit__(self, *exc):
        for k, v in self._saved.items():
            if v is None:
                os.environ.pop(k, None)
            else:
                os.environ[k] = v


def _seed_openrouter(state_dir: Path) -> None:
    from halo_harness.providers.databricks import write_models_json
    write_models_json(state_dir, [
        {"id": "v/eyes", "context_length": 1_000_000, "input_modalities": ["text", "image", "file"],
         "output_modalities": ["text"], "supported_parameters": ["tools", "reasoning"],
         "pricing": {"prompt": "0.000003", "completion": "0.000015"}},
        {"id": "v/mystery", "context_length": 32_000},
    ])


@test
def test_takes_words_read_only_what_the_row_states(ctx: Ctx):
    from halo_harness.model_takes import takes_text, takes_words
    ctx.check(f"vision+pdf, tools, think, got {takes_words(EYES)}", takes_words(EYES) == ["text", "vision", "pdf", "tools", "think"])
    ctx.check(f"a text-only row says text, got {takes_words(PLAIN)}", takes_words(PLAIN) == ["text"])
    ctx.check(f"no stated inputs: ?, never blank, got {takes_words(BLANK)}", takes_words(BLANK) == ["?"] and takes_text(BLANK) == "?")
    every = {"modalities_in": ["video", "audio", "text", "image", "pdf"], "modalities_out": ["text", "image"]}
    ctx.check(f"the fixed order, image out after the inputs, got {takes_words(every)}",
              takes_words(every) == ["text", "vision", "audio", "video", "pdf", "image"])
    probed = {"modalities_in": ["text"], "measured": {"tools_probe": True}}
    rejected = {"modalities_in": ["text"], "tools": True, "measured": {"tools_rejected": True}}
    ctx.check("tools when measured, not when a live 400 rejected them",
              takes_words(probed) == ["text", "tools"] and takes_words(rejected) == ["text"])
    ctx.check("only the tool flag stated: ? then tools", takes_words({"tools": True}) == ["?", "tools"])
    ctx.check("a reasoning kind of none is no think", takes_words({"modalities_in": ["text"], "reasoning": {"kind": "none"}}) == ["text"])


@test
def test_picker_row_puts_takes_after_the_ref_and_price_before_ctx_and_speed(ctx: Ctx):
    from rich.console import Console
    from rich.text import Text
    from halo_harness.model_display import PICKER_COLUMN_HEADER, format_picker_row
    row = format_picker_row(EYES)
    ctx.check(f"the vision+pdf row, got {row!r}", "takes=text,vision,pdf,tools,think in=$3.00/M" in row)
    ctx.check(f"text only, got {format_picker_row(PLAIN)!r}", "takes=text " in format_picker_row(PLAIN))
    blank = format_picker_row(BLANK)
    ctx.check(f"no stated inputs: takes=?, got {blank!r}", "takes=? " in blank and "speed=?" in blank)
    at = [row.index(k) for k in ("or:v/eyes", "takes=", "in=", "out=", "ctx=", "speed=")]
    ctx.check(f"ref, takes, price, then ctx and speed, got {at}", at == sorted(at))
    console = Console(file=io.StringIO(), width=100, color_system=None, legacy_windows=False)
    console.print(Text(row, no_wrap=True, overflow="ellipsis"), no_wrap=True, overflow="ellipsis")  # the picker's Text
    narrow = console.file.getvalue()
    ctx.check(f"a narrow terminal keeps ref, takes and price, cuts ctx and speed, got {narrow!r}",
              "takes=text,vision,pdf,tools,think" in narrow and "out=$15.00/M" in narrow and "speed=" not in narrow
              and len(narrow.splitlines()) == 1)
    ctx.check(f"the header explains the column, got {PICKER_COLUMN_HEADER!r}",
              PICKER_COLUMN_HEADER.startswith("takes = what it reads") and "? = not known" in PICKER_COLUMN_HEADER)


@test
def test_confirmation_suffix_reads_the_best_at_cache(ctx: Ctx):
    from halo_harness.model_takes import confirm_suffix, takes_for_ref
    from halo_harness.models_best_at import rebuild
    with _Env() as env:
        rebuild(env.state_dir, [EYES, PLAIN])
        ctx.check(f"a cached ref, got {confirm_suffix(['or:v/eyes'], env.state_dir)!r}",
                  confirm_suffix(["or:v/eyes"], env.state_dir) == " · takes text,vision,pdf,tools,think")
        ctx.check("an alias falls through to the resolved ref",
                  confirm_suffix(["eyes-alias", "or:v/eyes"], env.state_dir).endswith("takes text,vision,pdf,tools,think"))
        ctx.check("an unknown ref: ?", confirm_suffix(["or:v/nope"], env.state_dir) == " · takes ?")
        words, line = takes_for_ref("or:v/eyes", env.state_dir)
        ctx.check(f"the honest line comes with it, got {line!r}", line.startswith("vision+pdf in, tools, reasoning"))


@test
def test_halo_models_prints_a_takes_column(ctx: Ctx):
    from halo_harness.catalog_cli import cmd_models
    with _Env() as env:
        _seed_openrouter(env.state_dir)
        buf = io.StringIO()
        with redirect_stdout(buf):
            rc = cmd_models([])
        out = buf.getvalue().splitlines()
        head = next((ln for ln in out if ln.startswith("id ")), "")
        eyes = next((ln for ln in out if ln.startswith("v/eyes")), "")
        mystery = next((ln for ln in out if ln.startswith("v/mystery")), "")
        ctx.check(f"rc 0 and the header names takes, got {rc} / {head!r}", rc == 0 and " takes " in head and "? = not stated" in head)
        ctx.check(f"the stated row, got {eyes!r}", eyes.rstrip().endswith("text,vision,pdf,tools,think") and "$3.00/M" in eyes)
        ctx.check(f"no stated inputs: ?, the prices still blank, got {mystery!r}",
                  mystery.rstrip().endswith("?") and "$" not in mystery)


@test
def test_databricks_table_carries_takes_from_the_facts(ctx: Ctx):
    from halo_harness.catalog_cli import format_dbx_table_lines
    rows = {"databricks-eyes": {"family": "claude", "path_type": "anthropic", "chat": True, "context_tokens": 200_000,
                                "facts": {"modalities_in": ["text", "image", "pdf"], "tools": True}},
            "databricks-bare": {"family": "other", "path_type": "invocations", "chat": True}}
    lines = format_dbx_table_lines(rows)
    ctx.check(f"the header names takes, got {lines[0]!r}", lines[0].rstrip().endswith("takes"))
    eyes = next(ln for ln in lines if ln.startswith("databricks-eyes"))
    bare = next(ln for ln in lines if ln.startswith("databricks-bare"))
    ctx.check(f"the facts' takes, got {eyes!r}", "text,vision,pdf,tools" in eyes)
    ctx.check(f"none stated: ?, got {bare!r}", bare.rstrip().endswith("?"))


@test
def test_halo_models_show_prints_the_honest_line(ctx: Ctx):
    from halo_harness.catalog_cli import cmd_models
    from halo_harness.models_best_at import rebuild
    with _Env() as env:
        rebuild(env.state_dir, [EYES])
        buf = io.StringIO()
        with redirect_stdout(buf):
            rc = cmd_models(["show", "or:v/eyes"])
        text = buf.getvalue()
        ctx.check(f"takes and the line, got {text!r}", rc == 0 and "takes: text,vision,pdf,tools,think" in text
                  and "best at: vision+pdf in, tools, reasoning" in text)
        buf = io.StringIO()
        with redirect_stdout(buf):
            cmd_models(["show", "or:v/eyes", "--json"])
        got = json.loads(buf.getvalue())
        ctx.check(f"--json carries both, got {got.get('takes')} / {got.get('best_at_line')!r}",
                  got.get("takes") == ["text", "vision", "pdf", "tools", "think"] and got.get("best_at_line", "").startswith("vision+pdf"))


@test
def test_studio_rows_carry_takes(ctx: Ctx):
    from halo_harness.studio import model as M
    from halo_harness.studio.sessions_new_api import get_new
    from halo_harness.studio.setup_state import model_list
    with _Env() as env:
        _seed_openrouter(env.state_dir)
        cwd = env.home / "proj"
        cwd.mkdir()
        rows = {r["ref"]: r for r in M.model_rows(env.state_dir, cwd, cached=True)}
        ctx.check(f"GET models: takes on every row, got {[(k, r.get('takes')) for k, r in rows.items()]}",
                  rows.get("or:v/eyes", {}).get("takes") == ["text", "vision", "pdf", "tools", "think"]
                  and rows.get("or:v/mystery", {}).get("takes") == ["?"])
        setup = {r["ref"]: r for r in model_list(env.state_dir, cwd)}
        ctx.check("Setup's rows too", setup.get("or:v/eyes", {}).get("takes") == ["text", "vision", "pdf", "tools", "think"])
        status, body = get_new(SimpleNamespace(state_dir=env.state_dir, cwd=cwd))
        new = {r["ref"]: r for r in body.get("models") or []}
        ctx.check(f"the new-session rows carry takes and the line, got {new.get('or:v/eyes')}",
                  status == 200 and new.get("or:v/eyes", {}).get("takes") == ["text", "vision", "pdf", "tools", "think"]
                  and new["or:v/eyes"].get("line", "").startswith("vision+pdf"))


if __name__ == "__main__":
    ctx = Ctx()
    results, passed, failed, skipped = run_all(TESTS, ctx)
    sys.exit(print_results(results, passed, failed, skipped, label="model takes"))
