// The reviewers' owner-proof probes as a pack's page script (Halo 3.4.1.2, SERVERS-4 and PACKS-2 fixture). At import:
// patch every shared intrinsic the shell might hand its proof through, and keep each 64-hex string seen. On demand:
// open Studio's own page in a window and read its salt before the shell removes it, then forge an owner write with
// every salt and every caught value. tests/helpers/studio_owner_probe.py drives it; every forgery must be refused.
const P = (window.__probe = { salts: [], stolen: [], opened: false, openDone: false, viewOnly: false, severed: false, mounted: false });
const HEX = /^[0-9a-f]{64}$/;
const look = (v) => {
  if (typeof v === "string" && HEX.test(v) && !P.stolen.includes(v)) P.stolen.push(v);
};
const scan = (o) => {
  try {
    if (o && typeof o === "object") for (const k of Object.keys(o)) look(o[k]);
  } catch {
    /* not readable */
  }
};
const realThen = Promise.prototype.then;
const realGet = Map.prototype.get;
Map.prototype.get = function (k) {
  look(k);
  const v = realGet.call(this, k);
  look(v);
  if (v && typeof v.then === "function") realThen.call(v, look, () => undefined);
  return v;
};
Promise.prototype.then = function (ok, bad) {
  return realThen.call(this, (v) => (look(v), typeof ok === "function" ? ok(v) : v), bad);
};
for (const name of ["set", "append"]) {
  const real = Headers.prototype[name];
  Headers.prototype[name] = function (k, v) {
    look(v);
    return real.call(this, k, v);
  };
}
for (const field of ["signal", "referrerPolicy", "integrity", "keepalive", "duplex"]) { // fields only fetch's init has
  try {
    Object.defineProperty(Object.prototype, field, { configurable: true, get() { scan(this); scan(this && this.headers); return undefined; } });
  } catch {
    /* already defined */
  }
}

async function hmac(token, salt) {
  const enc = new TextEncoder();
  const key = await crypto.subtle.importKey("raw", enc.encode(token), { name: "HMAC", hash: "SHA-256" }, false, ["sign"]);
  const bytes = new Uint8Array(await crypto.subtle.sign("HMAC", key, enc.encode(salt)));
  return Array.from(bytes, (b) => (b < 16 ? "0" : "") + b.toString(16)).join("");
}

window.__probeOpen = () => {
  const w = window.open("/?mode=settings");
  P.opened = !!w;
  const t0 = Date.now();
  const poll = () => {
    try {
      const s = w.document.documentElement.dataset.ownerSalt;
      if (s && !P.salts.includes(s)) P.salts.push(s);
      if (w.document.querySelector('[data-testid="owner-note"]')) P.viewOnly = true;
    } catch {
      /* not loaded yet */
    }
    try {
      if (Date.now() - t0 > 1500 && (w.closed || w.document === undefined)) P.severed = true;
    } catch {
      P.severed = Date.now() - t0 > 1500;
    }
    if (Date.now() - t0 < 8000 && !P.viewOnly && !P.severed) setTimeout(poll, 2);
    else P.openDone = true;
  };
  poll();
};

window.__probeForge = async (pack) => {
  const token = sessionStorage.getItem("halo-studio-token") || "";
  const proofs = [""];
  for (const s of P.salts) proofs.push(await hmac(token, s));
  for (const v of P.stolen) proofs.push(v);
  const out = [];
  for (const proof of proofs) {
    const r = await fetch("/api/pack/" + pack + "/grant", { method: "POST", body: JSON.stringify({ need: "studio-script", on: false }),
      headers: { Authorization: "Bearer " + token, "Content-Type": "application/json", "X-Halo-Owner": proof } });
    out.push(r.status);
  }
  return out;
};

export function mount(el) {
  P.mounted = true;
  const p = document.createElement("p");
  p.dataset.testid = "owner-probe-ready";
  p.textContent = "probe armed";
  el.appendChild(p);
  return () => p.remove();
}
