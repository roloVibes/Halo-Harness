// The owner proof (3.3.14.0 R1, the review's #4; 3.4.1.2, SERVERS-4 / PACKS-2; studio/owner_proof.py,
// docs/STUDIO-shell.md "The owner's page and a pack's key"). Studio serves a per-launch salt as `data-owner-salt` on
// <html> only to a navigation the person made (the address bar, `halo studio` opening the browser, the browser's
// reload), never to a window a script opened, a frame or a fetch. This module reads it and removes it when the shell's
// script first runs, makes the proof (hex HMAC-SHA256 of the salt keyed by the launch token) at once, and keeps it as
// a plain string in this closure: no Map, no promise of it, no shared prototype method at use, never exported through
// packlib/, never on globalThis, never in storage. A pack's module is imported only after `ownerReady()` settles
// (routes/packs/importPack.ts), so no pack script runs while the proof is being made. The functions it calls are
// taken here, at boot, before any pack can replace them.

let salt = "";
try {
  const root = document.documentElement;
  salt = root.dataset.ownerSalt || "";
  delete root.dataset.ownerSalt;
} catch {
  salt = "";
}

const subtle = typeof crypto !== "undefined" ? crypto.subtle : undefined;
const importKey = subtle ? subtle.importKey.bind(subtle) : null;
const sign = subtle ? subtle.sign.bind(subtle) : null;
const encoder = new TextEncoder();
const encode = encoder.encode.bind(encoder);
const toHex = (n: number) => (n < 16 ? "0" : "") + n.toString(16);
let made = ""; // the token the proof was made for
let proof = ""; // the proof itself, once made
let ready: Promise<void> = Promise.resolve();

async function compute(token: string): Promise<void> {
  if (!importKey || !sign || !salt || !token) return;
  const key = await importKey("raw", encode(token), { name: "HMAC", hash: "SHA-256" }, false, ["sign"]);
  const bytes = new Uint8Array(await sign("HMAC", key, encode(salt)));
  let out = "";
  for (let i = 0; i < bytes.length; i++) out += toHex(bytes[i]);
  made = token;
  proof = out;
}

/** Make the proof for the launch token, once, at boot (lib/api.ts). Later tokens get none: a page Studio served for
 *  another launch must be opened again from Studio. */
export function makeOwnerProof(token: string): void {
  if (made || !token) return;
  ready = compute(token).catch(() => undefined);
}

/** Settles once the proof is made (or cannot be): a pack's module is imported only after it. */
export function ownerReady(): Promise<void> {
  return ready;
}

/** The `X-Halo-Owner` value for `token`, now ("" when this page was served without a salt: a tab a script or a page
 *  opened, or a browser that sends no Fetch Metadata; or for a token the proof was not made for). */
export function ownerProof(token: string): string {
  return token && token === made ? proof : "";
}

/** Whether this page can make changes: Studio served it the salt (a page the person opened themselves). */
export function ownerPage(): boolean {
  return !!salt;
}
