"""tools/sync_glossary.py -- copy docs/GLOSSARY.md (the source) to the
packaged twin halo_harness/templates/glossary/GLOSSARY.md, which an
installed Halo reads (it ships no docs/ folder). Halo 3.1.1.0 R1.

    python tools/sync_glossary.py           write the twin (LF line endings)
    python tools/sync_glossary.py --check   exit 1 when the twin differs

tests/test_glossary.py fails when the two differ.
"""
from __future__ import annotations

import sys
from pathlib import Path

REPO = Path(__file__).resolve().parent.parent
SOURCE = REPO / "docs" / "GLOSSARY.md"
TWIN = REPO / "halo_harness" / "templates" / "glossary" / "GLOSSARY.md"


def lf(data: bytes) -> bytes:
    return data.replace(b"\r\n", b"\n")


def main(argv: list) -> int:
    source = lf(SOURCE.read_bytes())
    if "--check" in argv:
        same = TWIN.is_file() and lf(TWIN.read_bytes()) == source
        print("the glossary twin matches docs/GLOSSARY.md" if same else
              "the glossary twin differs: python tools/sync_glossary.py")
        return 0 if same else 1
    TWIN.parent.mkdir(parents=True, exist_ok=True)
    TWIN.write_bytes(source)
    print(f"wrote {TWIN.relative_to(REPO)} ({len(source)} bytes)")
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
