"""tests.test_studio_model_pickers -- Halo 3.4.1.3 "Pick, don't type" (the owner, 2026-11-12, at Agents -> Models ->
"Test a model", a bare text box on a box with 63 models: "I'm not going to be able to type out an entire string correctly
of a model ... All model searchers in studio need this."). Unit and source pins, no Chrome, no provider request:

1. GET models/check (the picker's "use a reference that is not listed" row) checks a typed ref with the session's own
   parser: or:vendor/model and ol:name:tag are good, a prefix Halo does not know names the ones it knows, a space or an
   empty ref says so;
2. the static check: no `<input>`, `<textarea>`, `<select>` (or the kit's text wrappers) in Studio's UI source or the
   design pack's is labelled or named as a model field unless it is the shared picker's own or on the allowlist below,
   each entry with its reason -- and no entry is stale;
3. every model field the inventory names goes through the one field (shared/ModelSelect.tsx) or the one list
   (shared/picker/ModelPicker.tsx); the old native model <select> and the "pick from the list" text box are gone;
4. the settings catalog: every key that names a model is kind model (a role's model and embeddings.model too), apart
   from the speech enums;
5. the 250-line cap on every file this round touched, and no colour literal in its CSS.
The Chrome half (the picker's keys, rows, empty state, "not listed" row and the Models panel's fit) is
tests/test_studio_model_pickers_ui.py.
Run: python -m tests.test_studio_model_pickers
"""
from __future__ import annotations

import os
import re
import shutil
import sys
import tempfile
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from tests.helpers.model_fields_scan import model_fields  # noqa: E402
from tests.helpers.runner import Ctx, new_registry, print_results, run_all  # noqa: E402

test, TESTS = new_registry()
REPO = Path(__file__).resolve().parent.parent
UI = REPO / "halo_harness" / "studio" / "ui" / "src"

# (file, a piece of the field's tag) -> why it is not the picker. Keep a reason per entry.
ALLOW = {
    ("routes/shared/picker/ModelPicker.tsx", "Search the models"): "the picker's own search box",
    ("routes/shared/picker/ModelPicker.tsx", "model-learned-kind"): "the picker's learned-for filter (task kinds, not models)",
    ("routes/shared/picker/NotListed.tsx", "A reference that is not listed"): "the picker's last row: a ref the catalog lacks, checked as typed",
    ("routes/local/LibraryPull.tsx", "local-pull-name"): "pull a model this host does not have yet: the Library list is its picker, this is its not-listed row",
    ("routes/local/HfPage.tsx", "local-hf-add-path"): "a folder of model files, not a model",
    ("routes/local/PoolRun.tsx", "pool-run-model"): "the files the pool can run (its recommendation), not the catalog; a pick, not typing",
    ("routes/local/TrafficView.tsx", "local-traffic-model-pick"): "a filter over the models the traffic ledger saw",
    ("routes/settings/OllamaBlock.tsx", "settings-ollama-model"): "automatic / none / the steward's own local list; the row under it is the picker",
    ("packs/design/studio/src/Thread.tsx", "design-send-box"): "the message to the design model, not a model field",
}


def _home():
    home = Path(tempfile.mkdtemp(prefix="model-check-"))
    os.environ["BRIDGE_TEST_HOME"] = str(home)
    os.environ["BRIDGE_TEST_NO_BACKGROUND_NET"] = "1"
    return home


@test
def test_models_check_uses_the_sessions_parser(ctx: Ctx):
    home = _home()
    saved = {k: os.environ.pop(k) for k in list(os.environ) if k.startswith(("OPENROUTER_", "HALO_PROVIDERS"))}
    try:
        from halo_harness.studio.api import Request, dispatch
        from halo_harness.studio.models_check import check_ref
        good = check_ref("or:vendor/model-a")
        ctx.check(f"or:vendor/model-a parses to OpenRouter, got {good}", good["ok"] and good["provider"] == "openrouter" and "OpenRouter" in good["line"])
        ol = check_ref("ol:qwen3:30b")
        ctx.check(f"ol:qwen3:30b parses to Ollama, got {ol}", ol["ok"] and ol["provider"] == "ollama" and ol["model"] == "qwen3:30b")
        bad = check_ref("zz:thing")
        ctx.check(f"an unknown prefix names the known ones, got {bad}", not bad["ok"] and "zz:" in bad["line"] and "or:" in bad["line"] and "ol:" in bad["line"])
        ctx.check("a space is refused", not check_ref("or:vendor/a b")["ok"])
        ctx.check("empty says what to type", not check_ref("")["ok"] and "type a reference" in check_ref("")["line"])
        ctx.check("ol: alone is the parser's own sentence", not check_ref("ol:")["ok"] and "ol:" in check_ref("ol:")["line"])
        state = home / ".halo"
        state.mkdir(exist_ok=True)
        status, body = dispatch(Request(owner=True, method="GET", path="models/check", query={"ref": "or:vendor/model-a"}, body={}, cwd=home, state_dir=state))
        ctx.check(f"GET models/check answers, got {status} {body}", status == 200 and body["ok"] and "prefixes" in body)
    finally:
        os.environ.update(saved)
        shutil.rmtree(home, ignore_errors=True)


@test
def test_no_free_text_model_field(ctx: Ctx):
    found = model_fields()
    used = set()
    for f, line, tag in found:
        hit = [k for k in ALLOW if f.endswith(k[0]) and k[1] in tag]
        used.update(hit)
        ctx.check(f"{f}:{line} is a model field that is not the shared picker (use routes/shared/ModelSelect.tsx, or allowlist it "
                  f"with a reason): {tag[:160]}", bool(hit))
    stale = [k for k in ALLOW if k not in used]
    ctx.check(f"no stale allowlist entry, got {stale}", not stale)
    ctx.check("every entry has its reason", all(len(v) > 10 for v in ALLOW.values()))


@test
def test_the_check_catches_a_new_free_text_model_field(ctx: Ctx):
    from tests.helpers import model_fields_scan as S
    for tag, want in (('<input className="input mono" placeholder="or:vendor/model" data-testid="x" />', True),
                      ('<TextIn label="Fallback model" value={v} onCommit={set} />', True),
                      ('<input placeholder="ol:qwen3:30b" />', True), ('<input aria-label="The working folder" />', False)):
        ctx.check(f"{tag}: flagged={want}", bool(S.MODEL.search(S.labels_of(S.opening_tag(tag, 0)))) == want)


@test
def test_every_model_field_goes_through_the_one_picker(ctx: Ctx):
    def src(rel):
        return (UI / rel).read_text(encoding="utf-8")
    for rel in ("routes/roles/Models.tsx", "routes/roles/BioFields.tsx", "routes/roles/BioSchedule.tsx", "routes/roles/SectionForm.tsx",
                "routes/settings/fields/ModelField.tsx", "routes/session/NewSession.tsx", "routes/packs/PackForm.tsx",
                "routes/roles/Assignment.tsx", "routes/roles/ModelStrip.tsx", "routes/roles/TierMenu.tsx", "routes/orchestra/GoalForm.tsx",
                "routes/orchestra/WorkflowForm.tsx"):
        ctx.check(f"{rel} uses ModelSelect", "<ModelSelect" in src(rel))
    for rel in ("routes/setup/DefaultModel.tsx", "routes/session/PromptComposer.tsx", "routes/shared/ModelSelect.tsx", "routes/orchestra/plan/Inspector.tsx"):
        ctx.check(f"{rel} draws the one list", "<ModelPicker" in src(rel))
    ms = src("routes/shared/ModelSelect.tsx")
    ctx.check("ModelSelect has no native <select> any more", "<select" not in ms and "msel-select" not in ms)
    ctx.check("ModelField has no text box any more", "TextField" not in src("routes/settings/fields/ModelField.tsx"))
    ctx.check("no Pick of catalog refs is left", not [p for p in UI.rglob("*.tsx") if re.search(r"options=\{\[\"\", \.\.\.(refs|models\.map)", p.read_text(encoding="utf-8"))])
    ctx.check("the old ModelPicker path re-exports the shared one", "shared/picker/ModelPicker" in src("routes/roles/ModelPicker.tsx"))
    for p in (REPO / "halo_harness" / "templates" / "packs" / "design" / "studio" / "src").rglob("*.tsx"):
        t = p.read_text(encoding="utf-8")
        if "model" in t and "ModelSelect" not in t:
            ctx.check(f"{p.name}: no model text field", not re.search(r"<input[^>]*model", t, re.I))


@test
def test_the_settings_catalog_types_model_keys(ctx: Ctx):
    from halo_harness.settings_catalog import leaf_kind, rows
    for r in rows():
        last = r.key.split(".")[-1]
        if re.search(r"model$", last, re.I) and last != "model_memory":
            ctx.check(f"{r.key} is kind model (or the speech enum), got {r.kind}", r.kind == "model" or r.key.startswith("voice."))
    role = next(r for r in rows() if r.key == "roles.<role>")
    ctx.check("a role's model is picked from the catalog", leaf_kind(role) == "model")


@test
def test_files_stay_under_the_cap(ctx: Ctx):
    for rel in ("routes/shared/picker/ModelPicker.tsx", "routes/shared/picker/PickerParts.tsx", "routes/shared/picker/NotListed.tsx",
                "routes/shared/picker/rows.ts", "routes/shared/picker/state.ts", "routes/shared/ModelSelect.tsx", "routes/roles/Models.tsx",
                "routes/settings/fields/ModelField.tsx", "routes/setup/DefaultModel.tsx", "routes/session/PromptComposer.tsx",
                "routes/session/NewSession.tsx", "routes/packs/PackForm.tsx", "styles/model-picker.css", "routes/roles/TestButton.tsx"):
        text = (UI / rel).read_text(encoding="utf-8")
        raw = re.findall(r"#[0-9a-fA-F]{3,8}\b|rgba?\(", re.sub(r"/\*.*?\*/", "", text, flags=re.S)) if rel.endswith(".css") else []
        ctx.check(f"{rel}: {len(text.splitlines())} lines <= 250, no colour literal {raw}", len(text.splitlines()) <= 250 and not raw)


if __name__ == "__main__":
    ctx = Ctx()
    results, passed, failed, skipped = run_all(TESTS, ctx)
    sys.exit(print_results(results, passed, failed, skipped))
