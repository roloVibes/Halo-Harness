// api.lib.util (3.3.13.0 R2, extension API 1.2): small pure helpers the shell uses -- structural sharing for polled
// JSON (`same`, `changed`: a store update that changes nothing redraws nothing) and box placement (`nudgeApart`).
export { changed, equal, reuse, same } from "../lib/diff";
export { nudgeApart, type Box } from "../lib/geometry";
