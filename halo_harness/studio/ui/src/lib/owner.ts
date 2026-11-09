// The owner proof (3.3.14.0 R1, the review's #4; studio/owner_proof.py, docs/STUDIO-shell.md "The owner's page and a
// pack's key"). The served index.html carries a per-launch salt as `data-owner-salt` on <html>; this module reads it
// once and removes it when the shell's script first runs, before any pack module can load (a pack's bundle is
// imported later, by PackView / PackEvents). `ownerHeader(token)` is the hex HMAC-SHA256 of the salt keyed by the
// launch token: lib/api.ts sends it as `X-Halo-Owner` on the shell's own requests, and Studio answers the routes that
// change grants, packs, Setup, Settings or sessions only with it. It lives in this module's closure: never exported
// through packlib/, never on globalThis, never in storage. The functions it calls are taken here, at boot, so a
// script that replaces them later does not see the salt.

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
const proofs = new Map<string, Promise<string>>();

function hex(buf: ArrayBuffer): string {
  const bytes = new Uint8Array(buf);
  let out = "";
  for (let i = 0; i < bytes.length; i++) out += (bytes[i] < 16 ? "0" : "") + bytes[i].toString(16);
  return out;
}

async function compute(token: string): Promise<string> {
  if (!importKey || !sign) return "";
  const key = await importKey("raw", encode(token), { name: "HMAC", hash: "SHA-256" }, false, ["sign"]);
  return hex(await sign("HMAC", key, encode(salt)));
}

/** The `X-Halo-Owner` value for `token` ("" when the page was served without a salt, or the browser has no WebCrypto). */
export function ownerHeader(token: string): Promise<string> {
  if (!salt || !token) return Promise.resolve("");
  let got = proofs.get(token);
  if (!got) {
    got = compute(token).catch(() => "");
    proofs.set(token, got);
  }
  return got;
}
