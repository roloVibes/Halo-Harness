"""tests.helpers.node_ts -- run a pure `.ts` module of Studio's UI in node, for the Python tests that pin one (the cost
agreement, the mode order, the model-name strip, the replay's time axis). Halo 3.4.1.1 (the 3.4.1.0 rounds' open item):

    run(js) -> the JSON of the last stdout line     js: an ES module that `await import(<file URL of a .ts>)`s and prints

Node 22.6+ runs a `.ts` with `--experimental-strip-types`. Debian's nodejs (the Linux VM's v24.21) is built WITHOUT
Node's TypeScript support (`process.features.typescript` is false: no amaro), so it throws ERR_NO_TYPESCRIPT. There
each imported `.ts` is transpiled first by the TypeScript compiler of the UI's own `node_modules` (`npm ci` under
halo_harness/studio/ui), to a scratch `.mjs`, and the same js runs on it. With neither, SkipTest says exactly what the
box lacks. The modules run this way have no runtime imports (their `import type` lines vanish either way).
"""
from __future__ import annotations

import json
import re
import shutil
import subprocess
import tempfile
from pathlib import Path

from tests.helpers.runner import SkipTest

UI = Path(__file__).resolve().parents[2] / "halo_harness" / "studio" / "ui"
TSC = UI / "node_modules" / "typescript"
_URL = re.compile(r"file:///[^'\"\s]+?\.ts\b")
TRANSPILE = """const ts = require(process.argv[1]); const fs = require('fs');
for (let i = 2; i < process.argv.length; i += 2) {
  const out = ts.transpileModule(fs.readFileSync(process.argv[i], 'utf8'),
    { compilerOptions: { module: ts.ModuleKind.ESNext, target: ts.ScriptTarget.ES2022, jsx: ts.JsxEmit.ReactJSX } });
  fs.writeFileSync(process.argv[i + 1], out.outputText);
}"""


def _node() -> str:
    node = shutil.which("node")
    if not node:
        raise SkipTest("no node on this box")
    return node


def _exec(node: str, flags: list, js: str) -> subprocess.CompletedProcess:
    return subprocess.run([node, *flags, "--no-warnings", "--input-type=module", "-e", js], capture_output=True,
                          encoding="utf-8", errors="replace", timeout=60)


def _transpiled(node: str, js: str, scratch: Path) -> str:
    from urllib.parse import unquote, urlparse
    pairs, args = {}, []
    for i, url in enumerate(dict.fromkeys(_URL.findall(js))):
        raw = unquote(urlparse(url).path)
        src = Path(raw[1:] if re.match(r"^/[A-Za-z]:", raw) else raw)
        dst = scratch / f"m{i}-{src.stem}.mjs"
        args += [str(src), str(dst)]
        pairs[url] = dst.resolve().as_uri()
    r = subprocess.run([node, "-e", TRANSPILE, str(TSC), *args], capture_output=True, encoding="utf-8", errors="replace", timeout=120)
    if r.returncode != 0:
        raise AssertionError(f"the TypeScript compiler in {TSC} failed: {r.stderr[-400:]}")
    for url, out in pairs.items():
        js = js.replace(url, out)
    return js


def run(js: str):
    """Run `js` (an ES module) and return the JSON its last stdout line prints; AssertionError with node's stderr."""
    node = _node()
    r = _exec(node, ["--experimental-strip-types"], js)
    if r.returncode != 0 and ("ERR_NO_TYPESCRIPT" in r.stderr or "strip-types" in r.stderr):
        version = (subprocess.run([node, "--version"], capture_output=True, text=True).stdout or "").strip()
        if not (TSC / "package.json").is_file():
            raise SkipTest(f"node {version} has no TypeScript support (built without it: Debian's) and "
                           f"{TSC.relative_to(UI.parents[2])} is not there to transpile with: `npm ci` under "
                           "halo_harness/studio/ui, or a Node 22.6+ from nodejs.org")
        with tempfile.TemporaryDirectory(prefix="halo-node-ts-") as d:
            r = _exec(node, [], _transpiled(node, js, Path(d)))
    if r.returncode != 0:
        raise AssertionError(f"node failed: {r.stderr[-600:]}")
    return json.loads((r.stdout or "null").strip().splitlines()[-1])
