"""tests.helpers.model_fields_scan -- find the form fields in Studio's UI source that are labelled or named as a model
field (Halo 3.4.1.3 "Pick, don't type"; tests/test_studio_model_pickers.py runs it).

A field is a JSX element that takes typed or chosen text: `<input`, `<textarea`, `<select`, and the kit's wrappers
(`<TextBox`, `<TextIn`, `<ListIn`, `<Pick`, `<TextField`). What labels or names it is read -- placeholder, aria-label,
label, title, name, id, data-testid / testid, as written in the source; it is a model field when those say "model",
carry a route prefix (`or:`, `ol:`, `dbx:` ...) or a model-shaped example (`vendor/model`, `hf.co/`). Every such field
must be the shared picker's own (its search box, its "not listed" row) or stand on the allowlist with its reason;
everything else goes through routes/shared/ModelSelect.tsx.
"""
from __future__ import annotations

import re
from pathlib import Path

REPO = Path(__file__).resolve().parent.parent.parent
ROOTS = [REPO / "halo_harness" / "studio" / "ui" / "src", REPO / "halo_harness" / "templates" / "packs" / "design" / "studio" / "src"]
TAGS = ("input", "textarea", "select", "TextBox", "TextIn", "ListIn", "Pick", "TextField")
_OPEN = re.compile(r"<(" + "|".join(TAGS) + r")\b")
_LABEL = re.compile(r"""\b(placeholder|aria-label|label|title|name|id|data-testid|testid)=(?:"([^"]*)"|\{`([^`]*)`\}|\{"([^"]*)"\})""")
MODEL = re.compile(r"model|\b(?:or|ol|oai|dbx|hf|ant|xp|cp|local):|hf\.co/|vendor/", re.I)


def opening_tag(text: str, at: int) -> str:
    """The opening tag from `at` to its closing `>` (or `/>`), skipping `>` inside braces and strings."""
    depth, quote, i = 0, "", at + 1
    while i < len(text):
        ch = text[i]
        if quote:
            if ch == "\\":
                i += 1
            elif ch == quote:
                quote = ""
        elif ch in "\"'`":
            quote = ch
        elif ch == "{":
            depth += 1
        elif ch == "}":
            depth -= 1
        elif ch == ">" and depth == 0 and text[i - 1] != "=":
            return text[at:i + 1]
        i += 1
    return text[at:]


def labels_of(tag: str) -> str:
    return " ".join("".join(g[1:]) for g in _LABEL.findall(tag))


def model_fields() -> "list[tuple[str, int, str]]":
    """(file relative to the repo, line, the opening tag) for every field labelled or named as a model field."""
    out = []
    for root in ROOTS:
        for p in sorted(root.rglob("*.tsx")):
            text = p.read_text(encoding="utf-8")
            for m in _OPEN.finditer(text):
                if text[max(0, m.start() - 2):m.start()].endswith("//") or text[m.start() - 1:m.start()].isalnum():
                    continue
                tag = opening_tag(text, m.start())
                if MODEL.search(labels_of(tag)):
                    out.append((str(p.relative_to(REPO)).replace("\\", "/"), text.count("\n", 0, m.start()) + 1, " ".join(tag.split())))
    return out


if __name__ == "__main__":
    for f, line, tag in model_fields():
        print(f"{f}:{line}: {tag[:200]}")
