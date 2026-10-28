"""tests.helpers.library_site -- Halo 3.3.5.0 R2: a fake ollama.com / registry / Hugging Face Hub for the library's
sources (halo_harness/models_library/cache.SEAMS["fetch"]): a url fragment -> a fixture file under
tests/fixtures/library (or a literal answer; None is a 404), every request recorded with its headers.
"""
from __future__ import annotations

from pathlib import Path

FIX = Path(__file__).resolve().parents[1] / "fixtures" / "library"


def text(name: str) -> str:
    return (FIX / name).read_text(encoding="utf-8")


class Site:
    """A fake site: url -> fixture text (None: 404), every request recorded with its headers."""

    def __init__(self, pages: dict):
        self.pages, self.got = pages, []

    def __call__(self, url, headers):
        self.got.append((url, headers))
        for key, name in self.pages.items():
            if key in url:
                return text(name) if name and (FIX / name).is_file() else name
        return None

    def __enter__(self):
        from halo_harness.models_library import cache
        cache.SEAMS["fetch"] = self
        return self

    def __exit__(self, *exc):
        from halo_harness.models_library import cache
        cache.SEAMS.clear()
