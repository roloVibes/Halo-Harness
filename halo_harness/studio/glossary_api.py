"""halo_harness.studio.glossary_api -- `GET /api/glossary`, the words Studio's
Glossary dialog lists and each section's help links (Halo 3.1.1.0 R1).

    GET glossary   {words: [{word, text}], source}

The paragraphs are docs/GLOSSARY.md's (halo_harness/glossary.py reads it,
or its packaged twin in an installed copy), the same `halo explain` and the
TUI's /explain show: Studio serves them, the bundle carries no copy.
"""

from __future__ import annotations


def get_glossary(req):
    from halo_harness import glossary as G
    words = G.load()
    return 200, {"words": [{"word": w, "text": t} for w, t in words.items()], "source": G.source_path().name}


def dispatch_glossary(req):
    if req.path != "glossary":
        return 404, {"error": f"no route for {req.method} /api/{req.path}"}
    if req.method != "GET":
        return 405, {"error": "/api/glossary answers GET"}
    return get_glossary(req)
