"""The design pack's own test, the kit's shape. Run it from the pack's folder:

    python -m tests.pack_test

It runs `halo_harness.ext.testing` -- every check `halo pack test .` makes (the manifest, the doctor on an installed
copy, the view module exports mount, the routes answer `GET ping` in shape, and each tests/test_*.py of the pack),
in a scratch home and project, never a model call, never the network -- then the pack's own checks below.
"""

import sys
from pathlib import Path

from halo_harness.ext import testing

PACK = Path(__file__).resolve().parent.parent


def own_checks(report) -> None:
    m = testing.manifest(PACK)
    report.add("pack.yaml", "the pack's id is design", m.get("id") == "design",
               "the id in pack.yaml is the pack's name everywhere: keep it as the folder's name")
    section = ((m.get("contributes") or {}).get("studio") or {}).get("sections", [{}])[0]
    report.add("pack.yaml", "the Design section is drawn whole by studio/design.js",
               (section.get("view") or {}).get("bundle") == "studio/design.js", "sections[0].view: {bundle: studio/design.js}")
    js = (PACK / "studio" / "design.js").read_text(encoding="utf-8") if (PACK / "studio" / "design.js").is_file() else ""
    report.add("studio/design.js", "the page module takes React from Studio (api.lib), never a copy of its own",
               "__haloStudioLib" in js and "useSyncExternalStore(" not in js, "build it with Halo's Studio UI: npm run build")
    report.add("server/routes.py", "the routes raise the body limit for a 15 MB asset (MAX_BODY)",
               "MAX_BODY = 22_000_000" in (PACK / "server" / "routes.py").read_text(encoding="utf-8"), "MAX_BODY = 22_000_000")


def main() -> int:
    report = testing.run(PACK)
    own_checks(report)
    print(report.text())
    return report.exit_code


if __name__ == "__main__":
    sys.exit(main())
