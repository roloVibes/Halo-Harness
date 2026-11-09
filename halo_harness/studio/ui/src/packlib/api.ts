// `@halo/api` and `api.lib`'s `api`, `fetchJson`, `authUrl` (3.3.13.0 R2, extension API 1.2; 3.3.14.0 R1, the
// review's #4 and #5: scoped to the pack, packlib/scoped.ts). A pack's page gets its own `scopedApi(pack, key)`: in
// its `mount(el, api)` as `api.lib`, and as `@halo/api` while its module is evaluated (the shell imports pack modules
// one at a time with the global set to that pack's lib, routes/packs/importPack.ts). This module's own exports are the
// client scoped to no pack (the global between imports): the read-only GETs, nothing of any pack's. They also give
// `@halo/api` its types.
import { scopedApi } from "./scoped";

export { ApiError, type Query } from "../lib/api";

const none = scopedApi("", "");

/** `api.get/post/put/del`: Studio's JSON client with the token, scoped to the pack. */
export const api = none.api;
/** One request (method, path under /api/, body, query), scoped the same way. */
export const call = none.call;
/** A JSON request under /api/; rejects with an ApiError carrying the server's line, or an Error naming the scope. */
export const fetchJson = none.fetchJson;
/** `/api/<path>` with the pack's key in `?k=`, for what sends no header: its own routes and files only. */
export const authUrl = none.authUrl;
