"""tests.helpers.node_ts -- run a pure `.ts` module of Studio's UI in node, for the Python tests that pin one (the cost
agreement, the mode order, the model-name strip, the replay's time axis). Halo 3.4.1.1 (the 3.4.1.0 rounds' open item):

    run(js) -> the JSON of the last stdout line     js: an ES module that `await import(<file URL of a .ts>)`s and prints

Node 22.6+ runs a `.ts` with `--experimental-strip-types`. Debian's nodejs (the Linux VM's v24.21) is built WITHOUT
Node's TypeScript support (`process.features.typescript` is false: no amaro), so it throws ERR_NO_TYPESCRIPT. There
each imported `.ts` is transpiled first by the TypeScript compiler of the UI's own `node_modules` (`npm ci` under
halo_harness/studio/ui), to a scratch `.mjs`, and the same js runs on it. With neither, SkipTest says exactly what the
box lacks. `HALO_NODE_TS_TRANSPILE=1` takes the transpile path on any node (to prove it on a box that has the other).

A loaded module may import a sibling at runtime the way the UI's source does, with no extension (`from "./layout"`;
3.6.0.2 R6): on the strip-types path a resolve hook retries such a relative specifier as `<specifier>.ts`; on the transpile
path every module a transpiled one imports relatively is transpiled into the same scratch folder too and its specifier
rewritten to that `.mjs` (`import type` lines vanish either way).
"""
from __future__ import annotations

import json
import os
import re
import shutil
import subprocess
import tempfile
from pathlib import Path

from tests.helpers.runner import SkipTest

UI = Path(__file__).resolve().parents[2] / "halo_harness" / "studio" / "ui"
TSC = UI / "node_modules" / "typescript"
_URL = re.compile(r"file:///[^'\"\s]+?\.ts\b")
TRANSPILE = r"""const ts = require(process.argv[1]); const fs = require('fs'); const path = require('path');
const dst = new Map(); const todo = [];
for (let i = 2; i < process.argv.length; i += 2) { dst.set(path.resolve(process.argv[i]), process.argv[i + 1]); todo.push(path.resolve(process.argv[i])); }
const dir = path.dirname(process.argv[3] || '.');
const SPEC = /(\bfrom\s*|\bimport\s*\(?\s*)(["'])(\.\.?\/[^"']+)\2/g;
const find = (from, spec) => {
  const base = path.resolve(path.dirname(from), spec);
  for (const p of [base, base + '.ts', base + '.tsx', path.join(base, 'index.ts')])
    if (/\.tsx?$/.test(p) && fs.existsSync(p) && fs.statSync(p).isFile()) return p;
  return null;
};
while (todo.length) {
  const src = todo.shift();
  let out = ts.transpileModule(fs.readFileSync(src, 'utf8'),
    { compilerOptions: { module: ts.ModuleKind.ESNext, target: ts.ScriptTarget.ES2022, jsx: ts.JsxEmit.ReactJSX } }).outputText;
  out = out.replace(SPEC, (all, head, q, spec) => {
    const dep = find(src, spec);
    if (!dep) return all;
    if (!dst.has(dep)) { dst.set(dep, path.join(dir, `m${dst.size}-${path.basename(dep).replace(/\.tsx?$/, '')}.mjs`)); todo.push(dep); }
    return head + q + './' + path.basename(dst.get(dep)) + q;
  });
  fs.writeFileSync(dst.get(src), out);
}"""
# The strip-types path's resolve hook: a relative specifier with no extension, imported from a `.ts`, is retried as `.ts`.
_HOOK = """export async function resolve(spec, ctx, next) {
  try { return await next(spec, ctx); } catch (e) {
    if (/^\\.\\.?\\//.test(spec) && !/\\.[cm]?[jt]sx?$/.test(spec) && /\\.tsx?$/.test(ctx.parentURL || '')) return next(spec + '.ts', ctx);
    throw e;
  }
}"""
_REGISTER = ("import { register as __haloRegister } from 'node:module';\n"
             f"__haloRegister('data:text/javascript,' + encodeURIComponent({json.dumps(_HOOK)}));\n")


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
    forced = os.environ.get("HALO_NODE_TS_TRANSPILE") == "1"
    r = None if forced else _exec(node, ["--experimental-strip-types"], _REGISTER + js)
    if r is None or (r.returncode != 0 and ("ERR_NO_TYPESCRIPT" in r.stderr or "strip-types" in r.stderr)):
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
