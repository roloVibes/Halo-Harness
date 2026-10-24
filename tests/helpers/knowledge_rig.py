"""tests.helpers.knowledge_rig -- what the knowledge tests share (Halo 3.1.8.0 R4):

* `home()` -- a fresh BRIDGE_TEST_HOME for one test (BRIDGE_STATE_DIR unset),
  yielding its `.halo` state dir, every variable restored after;
* `config(state, **values)` -- config.json keys under that state dir, a dotted
  key as a nested path (`config(state, **{"recall.sources": [...]})`);
* `embedder()` -- the fake embedder the recall tests use (test_coach_library_fleet
  patches embeddings_enabled / embed_texts the same way): a bag of words over
  VOCAB, so similar texts land near each other; `calls` counts the texts it
  embedded and `texts` keeps them. No model and no embedding model is ever called.
"""
from __future__ import annotations

import contextlib
import json
import os
import tempfile
from pathlib import Path

VOCAB = ["basket", "total", "decimal", "round", "pytest", "drum", "kali", "garden", "tomatoes", "vault", "obsidian",
         "money", "flaky", "cap", "plan", "recipe", "soup"]


@contextlib.contextmanager
def home(prefix: str = "know-"):
    saved = {k: os.environ.get(k) for k in ("BRIDGE_TEST_HOME", "BRIDGE_STATE_DIR")}
    d = Path(tempfile.mkdtemp(prefix=prefix))
    os.environ["BRIDGE_TEST_HOME"] = str(d)
    os.environ.pop("BRIDGE_STATE_DIR", None)
    try:
        (d / ".halo").mkdir(parents=True, exist_ok=True)
        yield d / ".halo"
    finally:
        for k, v in saved.items():
            os.environ.pop(k, None) if v is None else os.environ.__setitem__(k, v)


def config(state: Path, **values) -> None:
    path = Path(state) / "config.json"
    data = json.loads(path.read_text(encoding="utf-8")) if path.exists() else {}
    for key, value in values.items():
        cur = data
        parts = key.split(".")
        for part in parts[:-1]:
            cur = cur.setdefault(part, {})
        cur[parts[-1]] = value
    path.write_text(json.dumps(data), encoding="utf-8")


def vector(text: str) -> list:
    t = str(text).lower()
    return [1.0 if w in t else 0.0 for w in VOCAB]


class _Embedder:
    def __init__(self):
        self.calls, self.texts = 0, []

    def __call__(self, texts):
        self.calls += len(texts)
        self.texts += list(texts)
        return [vector(t) for t in texts]


@contextlib.contextmanager
def embedder():
    import halo_harness.providers.embeddings as EMB
    saved = (EMB.embeddings_enabled, EMB.embed_texts)
    fake = _Embedder()
    EMB.embeddings_enabled, EMB.embed_texts = (lambda: True), fake
    try:
        yield fake
    finally:
        EMB.embeddings_enabled, EMB.embed_texts = saved
