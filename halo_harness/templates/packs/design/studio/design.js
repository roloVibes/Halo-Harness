const fe = globalThis.__haloStudioLib;
if (!fe || !fe.jsxRuntime) throw new Error("this pack module runs inside Halo Studio: no shared jsxRuntime");
const n = fe.jsxRuntime, xe = globalThis.__haloStudioLib;
if (!xe || !xe.ReactDOM) throw new Error("this pack module runs inside Halo Studio: no shared ReactDOM");
const Nt = xe.ReactDOM, be = globalThis.__haloStudioLib;
if (!be || !be.api) throw new Error("this pack module runs inside Halo Studio: no shared api");
const D = be.api, De = "design", V = "design--design", Z = "packs/design/design";
function Te(e, t = "") {
  return D.authUrl(`${Z}/_files/${e}${t ? "?" + t : ""}`);
}
const ve = globalThis.__haloStudioLib;
if (!ve || !ve.store) throw new Error("this pack module runs inside Halo Studio: no shared store");
const b = ve.store, je = globalThis.__haloStudioLib;
if (!je || !je.util) throw new Error("this pack module runs inside Halo Studio: no shared util");
const Y = je.util, X = 380, St = 356, Ct = 420, ce = 40, Fe = 3, Q = {
  phone: { w: 390, h: 844, label: "Phone 390" },
  tablet: { w: 820, h: 1100, label: "Tablet 820" },
  desktop: { w: 1280, h: 800, label: "Desktop 1280" }
}, et = Object.keys(Q), tt = (e) => typeof e == "string" && e in Q;
function Oe(e) {
  const t = Q[e], s = Math.min(St / t.w, Ct / t.h);
  return { s, w: Math.round(t.w * s), h: Math.round(t.h * s) };
}
const te = (e) => Math.max(400, Oe(e).h + 190);
function ue(e, t, s) {
  const a = {}, o = te(s);
  let d = 0;
  for (const r of e)
    t[r.id] ? a[r.id] = t[r.id] : (a[r.id] = { x: 24 + d % Fe * (X + ce), y: 24 + Math.floor(d / Fe) * o }, d += 1);
  return a;
}
function $t(e, t, s, a) {
  const o = ue(e.filter((i) => !a.includes(i.id)), t, s), d = Math.max(24 - te(s), ...Object.values(o).map((i) => i.y)) + te(s), r = {};
  return a.forEach((i, l) => r[i] = { x: 24 + l * (X + ce), y: d }), r;
}
function He(e, t, s, a, o, d) {
  const r = te(s) - ce, i = (v) => ({ x: v.x, y: v.y, w: X, h: r }), l = ue(e, t, s), x = {};
  for (const v of e) v.id !== a && l[v.id] && (x[v.id] = i(l[v.id]));
  const g = Y.nudgeApart(i(o), x, { x: 0, y: 0, w: 1e6, h: 1e6 }, { minW: X, minH: r, gap: ce / 2, from: d ? i(d) : void 0 }), y = { [a]: o };
  for (const v of Object.keys(x)) (g[v].x !== x[v].x || g[v].y !== x[v].y) && (y[v] = { x: Math.round(g[v].x), y: Math.round(g[v].y) });
  return y;
}
const nt = "halo.studio.design.panel.design-artboards";
function Et() {
  try {
    const e = JSON.parse(localStorage.getItem(nt) || "{}").device;
    return tt(e) ? e : "desktop";
  } catch {
    return "desktop";
  }
}
const c = b.createStore({
  started: !1,
  projects: null,
  slug: "",
  data: null,
  loading: !1,
  error: "",
  turn: null,
  draft: "",
  positions: {},
  posFor: "",
  view: {},
  bust: {},
  sel: "",
  assets: [],
  dialog: null,
  busy: "",
  focusSend: 0,
  device: Et(),
  tool: "select",
  pinAt: null,
  pinOpen: "",
  editing: null,
  knobNote: {}
});
function st(e) {
  c.update(() => ({ device: e })), b.writeLocal(nt, JSON.stringify({ device: e }));
}
const le = (e) => c.update(() => ({ tool: e, pinAt: null, pinOpen: "", editing: null }));
function u(e) {
  return b.useStore(c, e);
}
const _ = (e) => c.update(() => ({ dialog: e })), $ = () => c.update(() => ({ dialog: null })), z = (e) => !!e.turn && !e.turn.done, Dt = (e) => e.projects !== null && e.projects.length === 0;
function Re(e, t) {
  var s;
  return (s = e.data) == null ? void 0 : s.artboards.find((a) => a.id === t);
}
const J = (e) => e == null ? "-" : "$" + Number(e).toFixed(e < 0.1 ? 4 : 2), Tt = (e) => e < 1024 ? e + " B" : e < 1048576 ? Math.round(e / 1024) + " KB" : (e / 1048576).toFixed(1) + " MB", ne = (e) => (e || []).map(([t, s]) => `${t} v${s}`).join(", ");
function Me(e, t, s, a = 0, o = 0) {
  const d = `${encodeURIComponent(e)}/${encodeURIComponent(t)}/${a ? "v" + a + "/" : ""}${encodeURIComponent(s)}`;
  return Te(d, o ? "b=" + o : "");
}
const Ot = (e, t) => Te(`${encodeURIComponent(e)}/_assets/${encodeURIComponent(t)}`), Ae = (e) => e.reduce((t, s) => t + (Number(s.cost) || 0), 0);
function Rt(e) {
  const t = e.data;
  if (!t) return e.projects && !e.projects.length ? "no design project yet" : "";
  const s = t.comments.filter((a) => !a.resolved).length;
  return `project: ${t.meta.name} · ${t.artboards.length} artboard(s) · ${s} open comment(s) · ${J(Ae(t.history))}${z(e) ? " · a turn runs" : ""}`;
}
const we = globalThis.__haloStudioLib;
if (!we || !we.events) throw new Error("this pack module runs inside Halo Studio: no shared events");
const pe = we.events, at = "halo.studio.design.project", Mt = 500;
let se = 0, Ue = 0;
const ot = (e) => e instanceof D.ApiError ? e.problems[0] || e.message : String(e), C = (e, t, s) => {
  const a = c.get().slug;
  return D.call(e, `${Z}/` + encodeURIComponent(a) + (t ? "/" + t : ""), s);
};
function Ge(e) {
  try {
    return localStorage.getItem(e) || "";
  } catch {
    return "";
  }
}
function Pe() {
  const e = Rt(c.get());
  b.studio.update((t) => t.status[V] === e ? {} : { status: { ...t.status, [V]: e } });
}
async function me() {
  try {
    const e = await D.api.get(`${Z}/projects`);
    e.moved && b.toast(e.moved, "info", 8e3);
    const t = Array.isArray(e.projects) ? e.projects : [];
    return c.update((s) => Y.changed(s, { projects: t, error: "" })), t;
  } catch (e) {
    return c.update((t) => ({ projects: t.projects ?? [], error: ot(e) })), c.get().projects || [];
  } finally {
    Pe();
  }
}
function At(e) {
  const t = e && typeof e == "object" && "nodes" in e ? e.nodes : e, s = {};
  for (const [a, o] of Object.entries(t || {})) o && typeof o.x == "number" && typeof o.y == "number" && (s[a] = { x: o.x, y: o.y });
  return s;
}
async function O() {
  const e = c.get().slug;
  if (e)
    try {
      const t = await C("GET", "");
      if (c.get().slug !== e) return;
      c.update((s) => {
        var o;
        const a = t.artboards.some((d) => d.id === s.sel) ? s.sel : ((o = t.artboards[0]) == null ? void 0 : o.id) || "";
        return Y.changed(s, { data: Y.same(s.data, t), sel: a, error: "" });
      }), t.live_turn && !c.get().turn && he(t.live_turn, "(a turn that was already running)");
    } catch (t) {
      c.update(() => ({ error: ot(t) }));
    } finally {
      Pe();
    }
}
async function rt() {
  try {
    const e = await C("GET", "assets");
    c.update((t) => Y.changed(t, { assets: e.assets || [] }));
  } catch {
    c.update((e) => Y.changed(e, { assets: [] }));
  }
}
async function ae(e) {
  b.writeLocal(at, e), window.clearTimeout(se), c.update(() => ({ slug: e, data: null, loading: !0, turn: null, view: {}, bust: {}, sel: "", assets: [], positions: {}, posFor: "", pinAt: null, pinOpen: "", editing: null, knobNote: {} })), await O(), c.update(() => ({ loading: !1 }));
  try {
    const t = await D.api.get("layout/" + encodeURIComponent("design:" + e));
    c.get().slug === e && c.update(() => ({ positions: At(t), posFor: e }));
  } catch {
    c.update(() => ({ posFor: e }));
  }
  rt();
}
function it(e) {
  c.update((t) => ({ positions: { ...t.positions, ...e } })), window.clearTimeout(Ue), Ue = window.setTimeout(() => {
    const t = c.get();
    if (!t.slug || !t.data) return;
    const s = {};
    for (const a of t.data.artboards) t.positions[a.id] && (s[a.id] = { x: Math.round(t.positions[a.id].x), y: Math.round(t.positions[a.id].y) });
    D.api.put("layout/" + encodeURIComponent("design:" + t.slug), { positions: s, nodes: s }).catch(() => null);
  }, Mt);
}
function dt(e, t, s) {
  c.update((a) => {
    if (!a.turn || a.turn.id !== e || a.turn.events[t]) return {};
    const o = a.turn.events.slice();
    return o[t] = s, { turn: { ...a.turn, events: o } };
  });
}
async function ye(e, t) {
  const s = c.get().turn;
  if (!s || s.id !== e || s.done) return;
  window.clearTimeout(se), c.update((o) => ({ turn: o.turn && { ...o.turn, done: !0, result: t }, bust: Pt(o.bust, t) }));
  const a = t || { code: 1 };
  a.cancelled ? b.toast("Turn cancelled: what it wrote so far is saved as versions", "info", 4500) : a.code === 0 ? b.toast(`Turn done: ${ne(a.versions) || "no artboard changed"}`, "done", 4500) : b.toast(`The turn ended with exit ${a.code}${a.error ? ": " + a.error : ""}`, "error", 6e3), await O(), c.update((o) => {
    var d;
    return ((d = o.turn) == null ? void 0 : d.id) === e ? { turn: null } : {};
  });
}
function Pt(e, t) {
  const s = { ...e };
  for (const [a] of (t == null ? void 0 : t.versions) || []) s[a] = (s[a] || 0) + 1;
  return s;
}
async function lt(e) {
  const t = c.get().turn;
  if (!t || t.id !== e || t.done) return;
  const s = t.events.findIndex((a) => !a) >= 0 ? t.events.findIndex((a) => !a) : t.events.length;
  try {
    const a = await C("GET", `turn/${e}?since=${s}`);
    if (a.events.forEach((o, d) => dt(e, s + d, o)), a.done) return void ye(e, a.result);
  } catch (a) {
    if (a instanceof D.ApiError && a.status === 404) return void ye(e, null);
  }
  se = window.setTimeout(() => void lt(e), pe.feedState() === "open" ? 3e3 : 500);
}
function he(e, t, s) {
  window.clearTimeout(se);
  const a = { id: e, prompt: t, events: [], done: !1, result: null, label: s };
  c.update(() => ({ turn: a })), Pe(), se = window.setTimeout(() => void lt(e), pe.feedState() === "open" ? 1500 : 300);
}
function _t(e) {
  const t = e.data || {};
  if (t.pack !== De || t.kind !== "turn") return;
  const s = t.data || {}, a = c.get();
  if (!(!s.turn || s.slug !== a.slug)) {
    if (s.state === "started" && !a.turn) return he(s.turn, s.prompt || "");
    !a.turn || a.turn.id !== s.turn || (s.state === "event" && typeof s.n == "number" && s.event ? dt(s.turn, s.n, s.event) : s.state === "done" && ye(s.turn, s.result || null));
  }
}
function _e() {
  c.get().started || (c.update(() => ({ started: !0 })), pe.onEvent("pack_live", _t), me().then((e) => {
    const t = Ge(at) || Ge("halo-design-project"), s = e.find((a) => a.slug === t) || e[0];
    s && ae(s.slug);
  }));
}
const ct = (e) => e instanceof D.ApiError ? e.problems[0] || e.message : String(e);
async function A(e, t, s) {
  c.update(() => ({ busy: e }));
  try {
    const a = await t();
    return s && b.toast(s(a), "done"), a;
  } catch (a) {
    return b.toast(ct(a), "error", 5e3), null;
  } finally {
    c.update(() => ({ busy: "" }));
  }
}
async function ut(e, t = "") {
  if (!e.trim()) return !1;
  const s = await A("new", () => D.api.post(`${Z}/projects`, { name: e.trim(), model: t }), () => `${e.trim()} created`);
  return s ? ($(), await me(), await ae(s.slug), c.update((a) => ({ focusSend: a.focusSend + 1 })), !0) : !1;
}
async function zt(e) {
  return await A("model", () => C("PUT", "model", { model: e }), (s) => s.model ? `This project runs on ${s.model} now` : "This project runs on the default model now") ? (await me(), await O(), !0) : !1;
}
async function ge(e = c.get().draft, t = {}, s) {
  const a = c.get(), o = e.trim();
  if (!a.slug) return b.toast("Make or open a project first", "info"), null;
  if (!o) return c.update((r) => ({ focusSend: r.focusSend + 1 })), null;
  if (z(a)) return b.toast("A turn already runs in this project: wait for it, or Cancel turn", "info"), null;
  const d = await A("send", () => C("POST", "run", { prompt: o, ...t }));
  return d && (e === a.draft && c.update(() => ({ draft: "" })), he(d.turn, o, s)), null;
}
async function pt() {
  const e = c.get().turn;
  !e || e.done || await A("cancel", () => C("POST", `turn/${e.id}/cancel`), () => "Stopping the turn...");
}
async function mt() {
  var r;
  const e = c.get().data, t = ((e == null ? void 0 : e.comments) || []).filter((i) => !i.resolved);
  if (!t.length) return b.toast("No open comments to send", "info");
  const s = t.map((i) => `- [${i.artboard}] ${i.path ? i.path + " " : ""}at ${Math.round(i.x)}%,${Math.round(i.y)}% of the frame: ${i.text}`);
  await ge(`Address these comments:
` + s.join(`
`), {}, `${t.length} comment(s)`);
  const a = t.map((i) => i.id), o = (r = c.get().turn) == null ? void 0 : r.id;
  if (!o) return;
  const d = c.subscribe(() => {
    var l;
    const i = c.get().turn;
    i && i.id === o && !i.done || (d(), i && i.id === o && ((l = i.result) == null ? void 0 : l.code) === 0 && !i.result.cancelled && C("POST", "comments/resolve", { ids: a }).then(() => O(), () => null));
  });
}
async function Lt(e) {
  if (z(c.get())) return b.toast("A turn already runs in this project", "info");
  const t = await A("critique", () => C("POST", "critique", { artboard: e }), () => `A second model reads ${e} and pins its notes`);
  t && he(t.turn, `Critique ${e}`, "critique");
}
async function It(e) {
  _({ kind: "contrast", aid: e, data: null });
  try {
    const t = await C("GET", `artboard/${encodeURIComponent(e)}/contrast`);
    c.update((s) => {
      var a;
      return ((a = s.dialog) == null ? void 0 : a.kind) === "contrast" && s.dialog.aid === e ? { dialog: { kind: "contrast", aid: e, data: t } } : {};
    });
  } catch (t) {
    c.update((s) => {
      var a;
      return ((a = s.dialog) == null ? void 0 : a.kind) === "contrast" ? { dialog: { kind: "contrast", aid: e, data: null, error: ct(t) } } : {};
    });
  }
}
async function Bt(e, t) {
  await A("restore", () => C("POST", `artboard/${encodeURIComponent(e)}/restore`, { version: t }), () => `${e}: v${t} is the newest version again`) && (c.update((a) => {
    const o = { ...a.view };
    return delete o[e], { view: o, bust: { ...a.bust, [e]: (a.bust[e] || 0) + 1 } };
  }), await O());
}
async function Ft(e, t) {
  await A("rename", () => C("POST", `artboard/${encodeURIComponent(e)}/rename`, { name: t }), () => `Renamed to ${t}`) && ($(), await O());
}
async function Ht(e) {
  await A("delete", () => D.api.del(`${Z}/${encodeURIComponent(c.get().slug)}/artboard/${encodeURIComponent(e)}`), () => `${e} deleted`) && ($(), await O());
}
async function Ut(e, t = "") {
  const s = await A("export", () => C("POST", "export", { as: e, artboard: t }));
  s && _({ kind: "exported", as: e, lines: s.lines || [] });
}
async function ht() {
  const e = await A("handoff", () => C("POST", "handoff", {}));
  e && _({ kind: "handoff", path: e.path });
}
const Gt = (e) => new Promise((t, s) => {
  const a = new FileReader();
  a.onload = () => t(String(a.result).split(",", 2)[1] || ""), a.onerror = () => s(new Error("could not read " + e.name)), a.readAsDataURL(e);
});
async function We(e) {
  if (!c.get().slug) return b.toast("Open a project first", "info");
  for (const t of e) {
    const s = await A("upload", async () => C("POST", "assets", { name: t.name, data_base64: await Gt(t) }), (a) => `${a.path} uploaded`);
    s && gt(`Use ${s.path} `);
  }
  await rt();
}
function gt(e) {
  c.update((t) => ({ draft: (t.draft ? t.draft.replace(/\s+$/, "") + `
` : "") + e, focusSend: t.focusSend + 1 }));
}
const oe = (e) => e instanceof D.ApiError ? e.problems[0] || e.message : String(e), Ke = /* @__PURE__ */ new Map();
function Wt(e, t, s) {
  const a = e + "\0" + t;
  window.clearTimeout(Ke.get(a)), Ke.set(a, window.setTimeout(() => void Kt(e, t, s), 150));
}
async function Kt(e, t, s) {
  try {
    const a = await C("POST", "control", { artboard: e, name: t, value: s }), o = (a.versions || []).find(([r]) => r === e), d = a.queued ? "next turn" : o ? `v${o[1]}` : "no change";
    c.update((r) => ({ knobNote: { ...r.knobNote, [e]: d }, bust: o ? { ...r.bust, [e]: (r.bust[e] || 0) + 1 } : r.bust })), a.queued && b.toast(`${t} is saved: the next turn applies it`, "info"), await O();
  } catch (a) {
    b.toast(oe(a), "error", 5e3);
  }
}
async function qt(e) {
  const t = c.get().pinAt;
  if (!(!t || !e.trim())) {
    c.update(() => ({ busy: "comment" }));
    try {
      await C("POST", "comment", { artboard: t.aid, text: e.trim(), x: t.x, y: t.y, path: "" }), c.update(() => ({ pinAt: null })), b.toast(`Comment pinned on ${t.aid}: Send comments turns the open pins into one turn`, "done"), await O();
    } catch (s) {
      b.toast(oe(s), "error", 5e3);
    } finally {
      c.update(() => ({ busy: "" }));
    }
  }
}
async function Vt(e) {
  try {
    await C("POST", "comments/resolve", { ids: [e] }), c.update(() => ({ pinOpen: "" })), b.toast("Comment resolved", "done"), await O();
  } catch (t) {
    b.toast(oe(t), "error", 5e3);
  }
}
async function Yt(e) {
  const t = e.trim();
  if (!t) return b.toast("Sync reads a folder path or a URL: type one first", "info"), !1;
  c.update(() => ({ busy: "sync" }));
  try {
    const s = await C("POST", "sync", { source: t }), a = Object.entries(s.system.tokens || {}).map(([o, d]) => [o, Object.keys(d).length]);
    return _({ kind: "synced", source: t, tokens: s.tokens, groups: a, sources: s.system.sources || [] }), await O(), !0;
  } catch (s) {
    return b.toast(oe(s), "error", 6e3), !1;
  } finally {
    c.update(() => ({ busy: "" }));
  }
}
async function Xt(e) {
  var a;
  const t = ((a = c.get().data) == null ? void 0 : a.system) || {}, s = {};
  for (const [o, d] of Object.entries(t.tokens || {})) s[o] = { ...d };
  for (const [o, d] of Object.entries(e)) {
    const [r, i] = o.split("\0");
    s[r] && i in s[r] && (s[r][i] = d);
  }
  try {
    return await C("PUT", "system", { system: { ...t, tokens: s } }), b.toast("Design system saved: the next turn uses it", "done"), await O(), !0;
  } catch (o) {
    return b.toast(oe(o), "error", 5e3), !1;
  }
}
const ft = (e) => e.trim().toLowerCase().replace(/[^a-z0-9-]+/g, "-").replace(/^-+|-+$/g, "").slice(0, 24) || "direction";
async function xt(e = "", t = 3) {
  var r, i;
  const s = c.get();
  if (!s.draft.trim())
    return c.update((l) => ({ focusSend: l.focusSend + 1 })), b.toast("Write what to design in the message box, then ask for 3 directions", "info");
  if (z(s)) return b.toast("A turn already runs in this project: wait for it, or Cancel turn", "info");
  const a = (((r = s.data) == null ? void 0 : r.artboards) || []).map((l) => l.id);
  await ge(s.draft, { variants: t, base: ft(e || s.sel || "direction") }, `${t} directions`);
  const o = (i = c.get().turn) == null ? void 0 : i.id;
  if (!o) return;
  const d = c.subscribe(() => {
    var y, v;
    const l = c.get().turn;
    if (l && l.id === o) return;
    d();
    const x = c.get(), g = (((y = x.data) == null ? void 0 : y.artboards) || []).map((k) => k.id).filter((k) => !a.includes(k));
    g.length && (it($t(((v = x.data) == null ? void 0 : v.artboards) || [], x.positions, x.device, g)), c.update(() => ({ sel: g[0] })), b.toast(`${g.length} direction(s) side by side: ${g.join(", ")}`, "done", 4500));
  });
}
function B(e) {
  return () => {
    b.goSection(V), _e(), window.setTimeout(e, 60);
  };
}
function Jt() {
  var o;
  const e = c.get(), t = "Design", s = ((o = e.data) == null ? void 0 : o.meta.name) || "the project", a = [
    { id: "design-new", group: t, label: "Design: new project", hint: "a name and, if you like, its model", run: B(() => _({ kind: "new" })) },
    { id: "design-send", group: t, label: "Design: send", hint: e.draft.trim() ? `run a turn in ${s}: "${e.draft.trim().slice(0, 40)}"` : "the message box: say what to make or change", run: B(() => void ge()) }
  ];
  if (a.push({ id: "design-directions", group: t, label: "Design: 3 directions", hint: e.draft.trim() ? `three different artboards of "${e.draft.trim().slice(0, 40)}"` : "of the message box's text: write it first", run: B(() => void xt()) }), z(e) && a.push({ id: "design-cancel", group: t, label: "Design: cancel turn", hint: `stop the turn running in ${s}`, run: () => void pt() }), e.data) {
    a.push(
      { id: "design-export", group: t, label: "Design: export", hint: "a folder, HTML, PNG, SVG or PDF", run: B(() => _({ kind: "export" })) },
      { id: "design-handoff", group: t, label: "Design: handoff bundle", hint: "the artboards, the system and HANDOFF.md for the next session", run: B(() => void ht()) }
    ), a.push({ id: "design-comment-tool", group: t, label: e.tool === "comment" ? "Design: stop pinning comments" : "Design: pin a comment", hint: "the Comment tool: click a frame to pin a comment there", run: B(() => le(c.get().tool === "comment" ? "select" : "comment")) });
    for (const r of et) r !== e.device && a.push({ id: "design-device-" + r, group: t, label: `Design: preview at ${Q[r].label}`, hint: "the size prototypes draw at", run: () => st(r) });
    const d = e.data.comments.filter((r) => !r.resolved).length;
    d && a.push({ id: "design-comments", group: t, label: `Design: send comments (${d})`, hint: "the open pins as one turn", run: B(() => void mt()) });
  }
  for (const d of (e.projects || []).slice(0, 30))
    d.slug !== e.slug && a.push({ id: "design-open-" + d.slug, group: t, label: `Design: open ${d.name}`, hint: `${d.artboards} artboard(s)`, run: B(() => void ae(d.slug)) });
  return a;
}
const ke = globalThis.__haloStudioLib;
if (!ke || !ke.React) throw new Error("this pack module runs inside Halo Studio: no shared React");
const f = ke.React, Ne = globalThis.__haloStudioLib;
if (!Ne || !Ne.widgets) throw new Error("this pack module runs inside Halo Studio: no shared widgets");
const S = Ne.widgets, Se = globalThis.__haloStudioLib;
if (!Se || !Se.ui) throw new Error("this pack module runs inside Halo Studio: no shared ui");
const h = Se.ui, Zt = (e) => e instanceof D.ApiError ? e.problems[0] || e.message : String(e), q = (e) => typeof e == "number" && isFinite(e) ? e : 0;
let qe = !1;
function Qt(e) {
  var r;
  const t = e.data;
  if (!t || t.type !== "halo-design-pick" || !Array.isArray(t.path) || typeof t.text != "string") return;
  const a = [...document.querySelectorAll('[data-testid="design-artboard"] iframe')].find((i) => i.contentWindow === e.source), o = (r = a == null ? void 0 : a.closest('[data-testid="design-artboard"]')) == null ? void 0 : r.dataset.id;
  if (!o || !t.text.trim()) return;
  const d = {
    aid: o,
    path: t.path.map((i) => Math.max(0, Math.floor(q(i)))),
    node: Math.floor(q(t.node ?? -1)),
    text: t.text,
    tag: String(t.tag || "text"),
    x: q(t.x),
    y: q(t.y),
    w: q(t.w),
    h: q(t.h)
  };
  c.update(() => ({ editing: d, sel: o, pinAt: null, pinOpen: "" }));
}
function en() {
  qe || (qe = !0, window.addEventListener("message", Qt));
}
const Ce = () => c.update(() => ({ editing: null }));
function tn(e) {
  var a;
  const t = [], s = e.ownerDocument.createTreeWalker(e, NodeFilter.SHOW_TEXT);
  for (let o = s.nextNode(); o; o = s.nextNode()) /^(script|style)$/i.test(((a = o.parentNode) == null ? void 0 : a.nodeName) || "") || t.push(o);
  return t;
}
function nn(e, t) {
  var d;
  const s = t.text.trim();
  let a = e.body;
  for (const r of t.path) a = a && a.children[r] || null;
  if (a) {
    const r = t.node >= 0 ? a.childNodes[t.node] : [...a.childNodes].find((i) => {
      var l;
      return i.nodeType === 3 && ((l = i.nodeValue) == null ? void 0 : l.trim());
    });
    if (r && r.nodeType === 3 && ((d = r.nodeValue) == null ? void 0 : d.trim()) === s) return r;
  }
  const o = e.body ? tn(e.body).filter((r) => {
    var i;
    return ((i = r.nodeValue) == null ? void 0 : i.trim()) === s;
  }) : [];
  return o.length === 1 ? o[0] : null;
}
function sn(e, t, s) {
  var r, i, l;
  const a = new DOMParser().parseFromString(e, "text/html"), o = nn(a, t);
  if (!o) return null;
  const d = o.nodeValue || "";
  return o.nodeValue = (((r = /^\s*/.exec(d)) == null ? void 0 : r[0]) || "") + s.trim() + (((i = /\s*$/.exec(d)) == null ? void 0 : i[0]) || ""), `<!doctype ${((l = a.doctype) == null ? void 0 : l.name) || "html"}>
` + a.documentElement.outerHTML;
}
async function an(e) {
  const t = c.get(), s = t.editing;
  if (s) {
    if (!e.trim() || e.trim() === s.text.trim()) return Ce();
    c.update(() => ({ busy: "text" }));
    try {
      const a = await fetch(Me(t.slug, s.aid, "index.html", 0, Date.now()), { cache: "no-store" });
      if (!a.ok) throw new Error(`could not read ${s.aid}'s page (HTTP ${a.status})`);
      const o = sn(await a.text(), s, e);
      if (!o) throw new Error("That text is drawn by the page's own script, not written in its source: change it with a turn instead");
      const r = ((await C("POST", "text-edit", { artboard: s.aid, html: o })).versions || []).find(([i]) => i === s.aid);
      c.update((i) => ({ editing: null, bust: { ...i.bust, [s.aid]: (i.bust[s.aid] || 0) + 1 } })), b.toast(r ? `Text saved as ${s.aid} v${r[1]}` : "No text changed", "done"), await O();
    } catch (a) {
      b.toast(Zt(a), "error", 6e3);
    } finally {
      c.update(() => ({ busy: "" }));
    }
  }
}
const Ve = (e) => Math.round(Math.max(0, Math.min(100, e)) * 10) / 10;
function bt(e, t) {
  return (s) => {
    s.key === "Escape" ? (s.preventDefault(), s.stopPropagation(), t()) : s.key === "Enter" && !s.shiftKey && !s.nativeEvent.isComposing && (s.preventDefault(), e());
  };
}
function on({ aid: e }) {
  const t = u((l) => {
    var x;
    return ((x = l.pinAt) == null ? void 0 : x.aid) === e ? l.pinAt : null;
  }), s = u((l) => l.busy === "comment"), [a, o] = f.useState(""), d = f.useRef(null);
  if (f.useEffect(() => {
    var l;
    o(""), t && ((l = d.current) == null || l.focus());
  }, [t]), !t) return null;
  const r = () => c.update(() => ({ pinAt: null })), i = () => void qt(a);
  return /* @__PURE__ */ n.jsxs(
    "form",
    {
      className: "da-pop",
      style: { left: `${t.x}%`, top: `${t.y}%` },
      "data-testid": "design-comment",
      onSubmit: (l) => (l.preventDefault(), i()),
      onPointerDown: (l) => l.stopPropagation(),
      onClick: (l) => l.stopPropagation(),
      children: [
        /* @__PURE__ */ n.jsx(
          "textarea",
          {
            ref: d,
            className: "input",
            rows: 3,
            value: a,
            onChange: (l) => o(l.target.value),
            onKeyDown: bt(i, r),
            placeholder: "What should change here?",
            "aria-label": "Comment text",
            "data-testid": "design-comment-text"
          }
        ),
        /* @__PURE__ */ n.jsxs("div", { className: "da-pop-row", children: [
          /* @__PURE__ */ n.jsx(h.Button, { size: "sm", variant: "ghost", type: "button", onClick: r, children: "Cancel" }),
          /* @__PURE__ */ n.jsx(h.Button, { size: "sm", variant: "primary", type: "submit", disabled: !a.trim() || s, "data-testid": "design-comment-save", children: "Pin comment" })
        ] })
      ]
    }
  );
}
function rn({ c: e, n: t }) {
  return /* @__PURE__ */ n.jsxs("div", { className: "da-pop", style: { left: `${e.x}%`, top: `${e.y}%` }, "data-testid": "design-pin-pop", onPointerDown: (s) => s.stopPropagation(), onClick: (s) => s.stopPropagation(), children: [
    /* @__PURE__ */ n.jsxs("div", { className: "da-pop-head mono muted", children: [
      "#",
      t,
      e.source === "critique" ? " · critique" : "",
      " · on v",
      e.version,
      /* @__PURE__ */ n.jsx("span", { className: "spacer" }),
      /* @__PURE__ */ n.jsx("button", { className: "icon-btn", "aria-label": "Close", onClick: () => c.update(() => ({ pinOpen: "" })), children: "x" })
    ] }),
    /* @__PURE__ */ n.jsx("p", { className: "da-pop-text", children: e.text }),
    /* @__PURE__ */ n.jsx("div", { className: "da-pop-row", children: /* @__PURE__ */ n.jsx(h.Button, { size: "sm", variant: "primary", onClick: () => void Vt(e.id), "data-testid": "design-resolve", children: "Resolve" }) })
  ] });
}
function dn({ aid: e, scale: t }) {
  const s = u((l) => {
    var x;
    return ((x = l.editing) == null ? void 0 : x.aid) === e ? l.editing : null;
  }), a = u((l) => l.busy === "text"), [o, d] = f.useState(""), r = f.useRef(null);
  if (f.useEffect(() => {
    d(s ? s.text.trim() : ""), s && window.setTimeout(() => {
      var l, x;
      return (l = r.current) == null || l.focus(), (x = r.current) == null ? void 0 : x.select();
    }, 0);
  }, [s]), !s) return null;
  const i = () => void an(o);
  return /* @__PURE__ */ n.jsxs(
    "form",
    {
      className: "da-pop da-edit",
      style: { left: s.x * t, top: s.y * t, minWidth: Math.max(200, s.w * t) },
      "data-testid": "design-text-edit",
      onSubmit: (l) => (l.preventDefault(), i()),
      onPointerDown: (l) => l.stopPropagation(),
      children: [
        /* @__PURE__ */ n.jsxs("div", { className: "da-pop-head mono muted", children: [
          "edit ",
          s.tag,
          " text"
        ] }),
        /* @__PURE__ */ n.jsx(
          "textarea",
          {
            ref: r,
            className: "input",
            rows: Math.min(5, Math.max(1, Math.ceil(o.length / 34))),
            value: o,
            onChange: (l) => d(l.target.value),
            onKeyDown: bt(i, Ce),
            "aria-label": "The text",
            "data-testid": "design-text-edit-input"
          }
        ),
        /* @__PURE__ */ n.jsxs("div", { className: "da-pop-row", children: [
          /* @__PURE__ */ n.jsx("span", { className: "mono muted", children: "Enter saves · Esc cancels" }),
          /* @__PURE__ */ n.jsx("span", { className: "spacer" }),
          /* @__PURE__ */ n.jsx(h.Button, { size: "sm", variant: "ghost", type: "button", onClick: Ce, children: "Cancel" }),
          /* @__PURE__ */ n.jsx(h.Button, { size: "sm", variant: "primary", type: "submit", disabled: a, "data-testid": "design-text-edit-save", children: "Save" })
        ] })
      ]
    }
  );
}
function ln({ aid: e, pins: t, scale: s }) {
  const a = u((r) => r.tool === "comment"), o = u((r) => t.some((i) => i.id === r.pinOpen) ? r.pinOpen : ""), d = (r) => {
    const i = r.currentTarget.getBoundingClientRect();
    !i.width || !i.height || c.update(() => ({ pinAt: { aid: e, x: Ve((r.clientX - i.left) / i.width * 100), y: Ve((r.clientY - i.top) / i.height * 100) }, pinOpen: "", sel: e }));
  };
  return /* @__PURE__ */ n.jsxs(n.Fragment, { children: [
    a && /* @__PURE__ */ n.jsx("div", { className: "da-overlay", onClick: d, title: "Click to pin a comment here", "data-testid": "design-comment-layer" }),
    t.map((r, i) => /* @__PURE__ */ n.jsx(
      "button",
      {
        className: "da-pin",
        "data-crit": r.source === "critique" || void 0,
        style: { left: `${r.x}%`, top: `${r.y}%` },
        "data-testid": "design-pin",
        title: r.text,
        "aria-label": `Comment ${i + 1}: ${r.text}`,
        "aria-expanded": o === r.id,
        onPointerDown: (l) => l.stopPropagation(),
        onClick: (l) => (l.stopPropagation(), c.update((x) => ({ pinOpen: x.pinOpen === r.id ? "" : r.id, pinAt: null }))),
        children: i + 1
      },
      r.id
    )),
    o && /* @__PURE__ */ n.jsx(rn, { c: t.find((r) => r.id === o), n: t.findIndex((r) => r.id === o) + 1 }),
    /* @__PURE__ */ n.jsx(on, { aid: e }),
    /* @__PURE__ */ n.jsx(dn, { aid: e, scale: s })
  ] });
}
function cn({ a: e, slug: t, n: s, bust: a, dev: o }) {
  if (!e.render) return /* @__PURE__ */ n.jsx("div", { className: "da-nofile muted", children: "no preview yet" });
  const d = s === e.latest, r = Me(t, e.id, e.render, d ? 0 : s, a);
  if (e.render === "index.html") {
    const i = Q[o], l = Oe(o), x = d ? r + (r.includes("?") ? "&" : "?") + "edit=pick" : r;
    return /* @__PURE__ */ n.jsx("div", { className: "da-scaler", style: { width: l.w, height: l.h }, children: /* @__PURE__ */ n.jsx("iframe", { sandbox: "allow-scripts", title: `${e.title || e.id} prototype`, src: x, style: { width: i.w, height: i.h, transform: `scale(${l.s})` } }) });
  }
  return /\.(png|svg)$/.test(e.render) ? /* @__PURE__ */ n.jsx("img", { className: "da-img", src: r, alt: `${e.title || e.id} render`, draggable: !1 }) : e.render.endsWith(".mp4") ? /* @__PURE__ */ n.jsx("video", { className: "da-img", src: r, controls: !0, muted: !0 }) : /* @__PURE__ */ n.jsxs("a", { className: "da-link", href: r, target: "_blank", rel: "noopener noreferrer", children: [
    /* @__PURE__ */ n.jsx("b", { children: e.render }),
    " ",
    /* @__PURE__ */ n.jsx("span", { className: "muted", children: "open it in a new tab" })
  ] });
}
function un(e) {
  c.update(() => ({ sel: e })), b.studio.update(() => ({ inspector: { section: V, panel: "design-artboards" } }));
}
const pn = f.memo(function({ a: t, slug: s, x: a, y: o, shown: d, bust: r, pins: i, selected: l, dragging: x, running: g, dev: y, onDown: v }) {
  const k = [...t.versions].sort((j, N) => j - N), T = d || t.latest, P = Math.max(0, k.indexOf(T)), E = T !== t.latest && t.latest > 0, L = t.render ? Me(s, t.id, t.render, E ? T : 0) : "", W = t.render === "index.html", m = Oe(y);
  return /* @__PURE__ */ n.jsxs(
    "article",
    {
      className: "da-card",
      style: { left: a, top: o, width: X },
      "data-testid": "design-artboard",
      "data-id": t.id,
      "data-device": W ? y : void 0,
      "data-selected": l || void 0,
      "data-dragging": x || void 0,
      onPointerDown: () => c.update((j) => j.sel === t.id ? {} : { sel: t.id }),
      children: [
        /* @__PURE__ */ n.jsxs("header", { className: "da-title", onPointerDown: (j) => v(j, t.id), title: "Drag to move", children: [
          /* @__PURE__ */ n.jsx("b", { children: t.title || t.id }),
          /* @__PURE__ */ n.jsx("span", { className: "og-chip mono", children: t.kind }),
          t.app && /* @__PURE__ */ n.jsx("span", { className: "og-chip mono", "data-app": !0, children: t.app }),
          /* @__PURE__ */ n.jsx("span", { className: "spacer" }),
          /* @__PURE__ */ n.jsxs("span", { className: "mono muted", "data-testid": "design-version", children: [
            "v",
            T || "-"
          ] })
        ] }),
        /* @__PURE__ */ n.jsxs("div", { className: "da-frame", style: W ? { width: m.w, height: m.h } : void 0, children: [
          /* @__PURE__ */ n.jsx(cn, { a: t, slug: s, n: T, bust: r, dev: y }),
          /* @__PURE__ */ n.jsx(ln, { aid: t.id, pins: i, scale: m.s })
        ] }),
        /* @__PURE__ */ n.jsxs("footer", { className: "da-foot", children: [
          k.length > 1 ? /* @__PURE__ */ n.jsxs("div", { className: "da-versions", children: [
            /* @__PURE__ */ n.jsx(
              "input",
              {
                type: "range",
                min: 0,
                max: k.length - 1,
                value: P,
                "aria-label": `Version of ${t.id}`,
                onChange: (j) => c.update((N) => ({ view: { ...N.view, [t.id]: k[Number(j.target.value)] }, editing: null }))
              }
            ),
            /* @__PURE__ */ n.jsx("span", { className: "mono muted", children: E ? `v${T} of ${t.latest}` : `v${T} (current)` }),
            E && /* @__PURE__ */ n.jsx(h.Button, { size: "sm", variant: "ghost", disabled: g, onClick: () => void Bt(t.id, T), children: "Restore" })
          ] }) : /* @__PURE__ */ n.jsx("span", { className: "mono muted", children: k.length ? `v${k[0]} (current)` : "no versions yet" }),
          /* @__PURE__ */ n.jsxs("div", { className: "da-actions", children: [
            t.controls.length > 0 && /* @__PURE__ */ n.jsxs(h.Button, { size: "sm", variant: "ghost", onClick: () => un(t.id), title: "Its knobs, in this panel's settings", "data-testid": "design-knobs", children: [
              "Knobs (",
              t.controls.length,
              ")"
            ] }),
            /* @__PURE__ */ n.jsx(h.Button, { size: "sm", variant: "ghost", disabled: g, onClick: () => void Lt(t.id), title: "A second model reads it and pins its notes", children: "Critique" }),
            /* @__PURE__ */ n.jsx(h.Button, { size: "sm", variant: "ghost", onClick: () => void It(t.id), title: "WCAG contrast of its text", children: "Contrast" }),
            /* @__PURE__ */ n.jsx(h.Button, { size: "sm", variant: "ghost", onClick: () => _({ kind: "rename", aid: t.id }), "data-testid": "design-rename", children: "Rename" }),
            /* @__PURE__ */ n.jsx(h.Button, { size: "sm", variant: "ghost", disabled: g, onClick: () => _({ kind: "delete", aid: t.id }), "data-testid": "design-delete", children: "Delete" }),
            L && /* @__PURE__ */ n.jsx("a", { className: "btn btn-ghost btn-sm", href: L, download: `${t.id}-v${T}-${t.render}`, children: /* @__PURE__ */ n.jsx("span", { className: "btn-label", children: "Download" }) })
          ] })
        ] })
      ]
    }
  );
});
function vt({ compact: e = !1 }) {
  const t = u((s) => s.device);
  return /* @__PURE__ */ n.jsx(
    "select",
    {
      className: e ? "input da-device" : "input",
      value: t,
      onChange: (s) => tt(s.target.value) && st(s.target.value),
      "aria-label": "Preview prototypes at",
      title: "The size a prototype is drawn at",
      "data-testid": "design-device",
      children: et.map((s) => /* @__PURE__ */ n.jsx("option", { value: s, children: Q[s].label }, s))
    }
  );
}
const mn = (e) => /^#[0-9a-fA-F]{6}$/.test(String(e)) ? String(e) : "#000000";
function hn({ aid: e, k: t }) {
  const [s, a] = f.useState(t.value), o = f.useRef(0);
  f.useEffect(() => {
    Date.now() - o.current > 1e3 && a(t.value);
  }, [t.value]);
  const d = (l) => (o.current = Date.now(), a(l), Wt(e, t.name, l)), r = String(t.target || "");
  let i;
  return t.kind === "color" ? i = /* @__PURE__ */ n.jsx("input", { type: "color", value: mn(s), onChange: (l) => d(l.target.value), "aria-label": t.name }) : t.kind === "select" ? i = /* @__PURE__ */ n.jsx("select", { className: "input", value: String(s ?? ""), onChange: (l) => d(l.target.value), "aria-label": t.name, children: (t.options || []).map((l) => /* @__PURE__ */ n.jsx("option", { value: String(l), children: String(l) }, String(l))) }) : i = /* @__PURE__ */ n.jsx("input", { type: "range", min: t.min ?? 0, max: t.max ?? 100, step: t.step || 1, value: Number(s ?? 0), onChange: (l) => d(Number(l.target.value)), "aria-label": t.name }), /* @__PURE__ */ n.jsxs("div", { className: "dk-row", "data-testid": "design-knob", "data-name": t.name, children: [
    /* @__PURE__ */ n.jsxs("div", { className: "dk-head", children: [
      /* @__PURE__ */ n.jsx("label", { children: t.name }),
      /* @__PURE__ */ n.jsxs("span", { className: "mono dk-value", children: [
        String(s ?? ""),
        t.kind !== "color" && t.kind !== "select" && t.unit ? t.unit : ""
      ] })
    ] }),
    i,
    /* @__PURE__ */ n.jsxs("div", { className: "mono muted dk-target", children: [
      r || "no target",
      r.startsWith("css:") ? " · applies at once" : " · applies on the next turn"
    ] })
  ] });
}
function gn() {
  const e = u((o) => {
    var d;
    return ((d = o.data) == null ? void 0 : d.artboards) || null;
  }), t = u((o) => o.sel), s = u((o) => {
    var d;
    return Re(o, o.sel) || ((d = o.data) == null ? void 0 : d.artboards[0]);
  }), a = u((o) => s && o.knobNote[s.id] || "");
  return /* @__PURE__ */ n.jsxs("div", { className: "og-settings dk", children: [
    /* @__PURE__ */ n.jsxs("label", { className: "fd-field", children: [
      /* @__PURE__ */ n.jsx("span", { className: "rail-label mono", children: "PREVIEW PROTOTYPES AT" }),
      /* @__PURE__ */ n.jsx(vt, {})
    ] }),
    !e || !s ? /* @__PURE__ */ n.jsx("p", { className: "muted", children: "Knobs belong to an artboard: open a project and run a turn first." }) : /* @__PURE__ */ n.jsxs(n.Fragment, { children: [
      /* @__PURE__ */ n.jsxs("label", { className: "fd-field", children: [
        /* @__PURE__ */ n.jsx("span", { className: "rail-label mono", children: "KNOBS OF" }),
        /* @__PURE__ */ n.jsx("select", { className: "input", value: s.id || t, onChange: (o) => c.update(() => ({ sel: o.target.value })), "aria-label": "Artboard", children: e.map((o) => /* @__PURE__ */ n.jsxs("option", { value: o.id, children: [
          o.title || o.id,
          " (",
          o.controls.length,
          ")"
        ] }, o.id)) })
      ] }),
      /* @__PURE__ */ n.jsxs("div", { className: "dk-ver mono muted", children: [
        s.title || s.id,
        " · now v",
        s.latest || "-",
        a && /* @__PURE__ */ n.jsx("span", { className: "og-chip mono", "data-testid": "design-knob-version", children: a === "next turn" ? "saved for the next turn" : `made ${a}` })
      ] }),
      s.controls.length ? s.controls.map((o) => /* @__PURE__ */ n.jsx(hn, { aid: s.id, k: o }, s.id + "/" + o.name)) : /* @__PURE__ */ n.jsxs("p", { className: "muted", children: [
        s.title || s.id,
        ' has no knobs yet. Ask for them in a turn: "add knobs for spacing and the accent colour".'
      ] })
    ] })
  ] });
}
function fn() {
  const e = u((p) => p.data), t = u((p) => p.slug), s = u((p) => p.positions), a = u((p) => p.view), o = u((p) => p.bust), d = u((p) => p.sel), r = u(z), i = u((p) => p.busy), l = u((p) => p.device), x = u((p) => p.tool), [g, y] = f.useState(null), [v, k] = f.useState(1), T = f.useRef(null), P = f.useRef(v);
  P.current = v;
  const E = f.useMemo(() => (e == null ? void 0 : e.artboards) || [], [e]), L = f.useMemo(() => {
    const p = ue(E, s, l);
    if (!g || !p[g.id]) return p;
    const w = { x: Math.max(0, p[g.id].x + g.dx), y: Math.max(0, p[g.id].y + g.dy) };
    return { ...p, ...He(E, s, l, g.id, w, p[g.id]) };
  }, [E, s, l, g]), W = f.useMemo(() => {
    const p = /* @__PURE__ */ new Map();
    for (const w of (e == null ? void 0 : e.comments) || []) w.resolved || p.set(w.artboard, [...p.get(w.artboard) || [], w]);
    return p;
  }, [e]), m = f.useMemo(() => {
    const p = Object.values(L);
    return { w: Math.max(700, ...p.map((w) => w.x + X + 60)), h: Math.max(420, ...p.map((w) => w.y + te(l) + 40)) };
  }, [L, l]), j = f.useCallback((p, w) => {
    if (p.button !== 0 || p.target.closest("button, select, input, a")) return;
    p.preventDefault(), p.stopPropagation(), c.update((M) => M.sel === w ? {} : { sel: w });
    const I = p.clientX, re = p.clientY;
    let K = { id: w, dx: 0, dy: 0 };
    const ze = (M) => {
      K = { id: w, dx: (M.clientX - I) / P.current, dy: (M.clientY - re) / P.current }, y(K);
    }, Le = () => {
      var Ie, Be;
      if (window.removeEventListener("pointermove", ze), window.removeEventListener("pointerup", Le), y(null), Math.hypot(K.dx, K.dy) < 3) return;
      const M = c.get(), ie = ue(((Ie = M.data) == null ? void 0 : Ie.artboards) || [], M.positions, M.device)[w];
      ie && it(He(((Be = M.data) == null ? void 0 : Be.artboards) || [], M.positions, M.device, w, { x: Math.max(0, ie.x + K.dx), y: Math.max(0, ie.y + K.dy) }, ie));
    };
    window.addEventListener("pointermove", ze), window.addEventListener("pointerup", Le);
  }, []);
  f.useEffect(() => {
    if (x !== "comment") return;
    const p = (w) => {
      var I, re;
      return w.key === "Escape" && !((re = (I = w.target) == null ? void 0 : I.closest) != null && re.call(I, "input, textarea, select")) && le("select");
    };
    return window.addEventListener("keydown", p), () => window.removeEventListener("keydown", p);
  }, [x]);
  const N = f.useRef("");
  f.useEffect(() => {
    const p = T.current;
    !p || !E.length || N.current === t || (N.current = t, (m.w > p.clientWidth || m.h > p.clientHeight) && k(Math.max(0.25, Math.min(1, (p.clientWidth - 24) / m.w, (p.clientHeight - 24) / m.h))));
  }, [t, E.length, m.w, m.h]);
  const F = () => {
    const p = T.current;
    p && k(Math.max(0.25, Math.min(1, (p.clientWidth - 24) / m.w, (p.clientHeight - 24) / m.h)));
  };
  return e ? /* @__PURE__ */ n.jsxs("div", { className: "da", children: [
    /* @__PURE__ */ n.jsxs("div", { className: "da-bar", children: [
      /* @__PURE__ */ n.jsxs("span", { className: "mono muted", children: [
        E.length,
        " artboard",
        E.length === 1 ? "" : "s"
      ] }),
      /* @__PURE__ */ n.jsxs("span", { className: "segmented", role: "group", "aria-label": "Canvas tool", children: [
        /* @__PURE__ */ n.jsx("button", { className: x === "select" ? "on" : "", "aria-pressed": x === "select", onClick: () => le("select"), title: "Select, drag, double-click a text to edit it", "data-testid": "design-tool-select", children: "Select" }),
        /* @__PURE__ */ n.jsx("button", { className: x === "comment" ? "on" : "", "aria-pressed": x === "comment", onClick: () => le(x === "comment" ? "select" : "comment"), title: "Click a frame to pin a comment there", "data-testid": "design-tool-comment", children: "Comment" })
      ] }),
      /* @__PURE__ */ n.jsx(vt, { compact: !0 }),
      /* @__PURE__ */ n.jsx("span", { className: "spacer" }),
      /* @__PURE__ */ n.jsx(h.Button, { size: "sm", variant: "ghost", onClick: F, title: "Fit every card in the panel", children: "Fit" }),
      /* @__PURE__ */ n.jsxs("span", { className: "segmented", role: "group", "aria-label": "Zoom", children: [
        /* @__PURE__ */ n.jsx("button", { onClick: () => k(Math.max(0.25, v / 1.2)), "aria-label": "Zoom out", children: "-" }),
        /* @__PURE__ */ n.jsxs("button", { onClick: () => k(1), title: "Back to 100%", children: [
          Math.round(v * 100),
          "%"
        ] }),
        /* @__PURE__ */ n.jsx("button", { onClick: () => k(Math.min(2, v * 1.2)), "aria-label": "Zoom in", children: "+" })
      ] }),
      /* @__PURE__ */ n.jsx(h.Button, { size: "sm", disabled: !E.length, onClick: () => _({ kind: "export" }), "data-testid": "design-export", children: "Export..." }),
      /* @__PURE__ */ n.jsx(h.Button, { size: "sm", disabled: i === "handoff", onClick: () => void ht(), "data-testid": "design-handoff", children: "Handoff" })
    ] }),
    E.length ? /* @__PURE__ */ n.jsx("div", { className: "da-scroll", ref: T, "data-tool": x, children: /* @__PURE__ */ n.jsx("div", { style: { width: m.w * v, height: m.h * v }, children: /* @__PURE__ */ n.jsx("div", { className: "da-world", style: { width: m.w, height: m.h, transform: `scale(${v})` }, children: E.map((p) => {
      const w = L[p.id], I = (g == null ? void 0 : g.id) === p.id ? g : null;
      return /* @__PURE__ */ n.jsx(
        pn,
        {
          a: p,
          slug: t,
          x: w.x,
          y: w.y,
          shown: a[p.id] || 0,
          bust: o[p.id] || 0,
          pins: W.get(p.id) || xn,
          selected: d === p.id,
          dragging: !!I,
          running: r,
          dev: l,
          onDown: j
        },
        p.id
      );
    }) }) }) }) : /* @__PURE__ */ n.jsx(h.Empty, { title: "No artboards yet", body: "Say what to design in the Thread panel: the first turn makes them." })
  ] }) : /* @__PURE__ */ n.jsx(h.Empty, { title: "No project open", body: "Pick one in Projects, or make a new one." });
}
const xn = [];
function bn() {
  const e = u((a) => {
    var o;
    return ((o = a.data) == null ? void 0 : o.artboards.length) || 0;
  }), t = u((a) => {
    var o;
    return (((o = a.data) == null ? void 0 : o.artboards) || []).reduce((d, r) => d + r.versions.length, 0);
  }), s = u((a) => {
    var o;
    return (((o = a.data) == null ? void 0 : o.comments) || []).filter((d) => !d.resolved).length;
  });
  return /* @__PURE__ */ n.jsx("div", { className: "glance", children: /* @__PURE__ */ n.jsxs("div", { className: "glance-numbers", children: [
    /* @__PURE__ */ n.jsx(S.Metric, { value: e, label: "artboards" }),
    /* @__PURE__ */ n.jsx(S.Metric, { value: t, label: "versions" }),
    /* @__PURE__ */ n.jsx(S.Metric, { value: s, label: "open pins", tone: s ? "warn" : void 0 })
  ] }) });
}
function vn() {
  const e = u(z), t = u((s) => {
    var a;
    return !!((a = s.data) != null && a.artboards.length);
  });
  return e ? "working" : t ? "idle" : "none";
}
const Ye = (e) => e.dataTransfer && [...e.dataTransfer.types].includes("Files") ? [...e.dataTransfer.files] : null;
function jn() {
  const e = u((r) => r.assets), t = u((r) => r.slug), s = u((r) => r.busy === "upload"), [a, o] = f.useState(!1), d = f.useRef(null);
  return t ? /* @__PURE__ */ n.jsxs(
    "div",
    {
      className: "das",
      "data-over": a || void 0,
      onDragOver: (r) => Ye(r) && (r.preventDefault(), o(!0)),
      onDragLeave: () => o(!1),
      onDrop: (r) => {
        o(!1);
        const i = Ye(r);
        i != null && i.length && (r.preventDefault(), We(i));
      },
      children: [
        /* @__PURE__ */ n.jsxs("div", { className: "das-bar", children: [
          /* @__PURE__ */ n.jsx(h.Button, { size: "sm", disabled: s, onClick: () => {
            var r;
            return (r = d.current) == null ? void 0 : r.click();
          }, "data-testid": "design-asset-add", children: "Add files..." }),
          /* @__PURE__ */ n.jsx("span", { className: "muted das-hint", children: "or drop them here" }),
          /* @__PURE__ */ n.jsx("input", { ref: d, type: "file", multiple: !0, hidden: !0, onChange: (r) => {
            const i = [...r.target.files || []];
            r.target.value = "", i.length && We(i);
          } })
        ] }),
        e.length ? /* @__PURE__ */ n.jsx("ul", { className: "das-list", children: e.map((r) => /* @__PURE__ */ n.jsxs("li", { className: "das-row", "data-testid": "design-asset", children: [
          /* @__PURE__ */ n.jsxs("button", { className: "das-pick", onClick: () => gt(`Use ${r.path} `), title: `Put ${r.path} in the message box`, children: [
            r.thumb ? /* @__PURE__ */ n.jsx("img", { src: r.thumb, alt: "" }) : /* @__PURE__ */ n.jsx("i", { className: "das-kind mono", children: r.kind }),
            /* @__PURE__ */ n.jsx("span", { className: "das-name", children: r.name }),
            /* @__PURE__ */ n.jsx("small", { className: "mono muted", children: Tt(r.size) })
          ] }),
          /* @__PURE__ */ n.jsx("a", { className: "btn btn-ghost btn-sm", href: Ot(t, r.name), download: r.name, "data-testid": "design-asset-download", children: /* @__PURE__ */ n.jsx("span", { className: "btn-label", children: "Download" }) })
        ] }, r.name)) }) : /* @__PURE__ */ n.jsx("p", { className: "muted das-empty", children: "No assets yet: logos, photos, fonts or captures for the turns to use." })
      ]
    }
  ) : /* @__PURE__ */ n.jsx(h.Empty, { title: "No project open", body: "Open a project to add the files its turns may use." });
}
function wn() {
  const e = u((t) => t.assets.length);
  return /* @__PURE__ */ n.jsxs("div", { className: "glance", children: [
    /* @__PURE__ */ n.jsx("div", { className: "glance-kicker mono", children: "ASSETS" }),
    /* @__PURE__ */ n.jsx("div", { className: "glance-text", children: e ? `${e} file${e === 1 ? "" : "s"}` : "none yet" })
  ] });
}
const ee = (...e) => e.join(`
`), yn = {
  what: "Prototypes, pages, decks and logos made by your own apps and models. A project is a folder of artboards in the design pack's data folder, and every turn saves a new version.",
  steps: [
    ["Make or open a project", "The Start view names the first one; then Projects lists them all, and New project makes another."],
    ["Say what to design", "Write it in Thread and press Enter: the reply streams in as the turn works; Cancel turn stops it."],
    ["Look and compare", "Artboards: drag a card by its title (the places are saved with the project), slide back through its versions, Restore one."],
    ["Pin comments, ask for notes", "Pick Comment and click a frame to pin a note; Critique has a second model pin its own; Contrast checks text against its background; Send comments turns the pins into a turn."],
    ["Change it by hand", "Double-click a text in a prototype to edit it in place; a card's Knobs; the Design system panel's tokens and Sync; Rename, Delete or Download an artboard."],
    ["Hand it off", "Export writes a folder, HTML, PNG, SVG or PDF; Handoff bundles it for the next Halo or Claude Code session."],
    ["Use your own files", "Assets: add or drop logos and photos; click one to put its path in the message."],
    ["Render pictures", "Render queues a ComfyUI workflow into an artboard of the project (halo media points Halo at ComfyUI)."]
  ]
}, kn = {
  "design-artboards": {
    about: "Every artboard of the project, with its versions, pins and knobs.",
    help: ee(
      "Drag a card by its title; double-click a text in a prototype to edit it (Enter saves a new version, Esc cancels).",
      "Comment, then click a frame, pins a comment there; click a pin for its text and Resolve.",
      "The device select draws prototypes at phone, tablet or desktop size; Settings keeps it.",
      "Knobs (on the card, or Settings) change spacing and colours at once, each a new version.",
      "The slider goes back through versions; Restore, Critique, Contrast, Rename, Delete, Export and Handoff."
    )
  },
  "design-thread": {
    about: "The project's turns: what you asked and what the model did.",
    help: ee(
      "Type what to make or change and press Enter (Shift+Enter: a new line).",
      "3 directions sends it as three different artboards, named after the box beside it.",
      "The reply streams in as the turn runs; Cancel turn stops it.",
      "Send comments turns the open pins into one turn."
    )
  },
  "design-system": {
    about: "The project's design system: the tokens every turn designs with.",
    help: ee(
      "Tokens by group (colours, type, spacing, radii); a colour shows its swatch.",
      "Edit a value and press Save tokens; the next turn uses it.",
      "Sync reads tokens from a codebase folder or a web page, then says what it found."
    )
  },
  "design-render": {
    about: "A ComfyUI workflow rendered into an artboard of this project.",
    help: ee(
      "Pick a workflow (a starter, or one saved on ComfyUI), fill its inputs, name the artboard and press Render.",
      "The render runs on the ComfyUI Halo is pointed at (halo media init); its steps show here as it goes.",
      "Each output becomes an artboard (or the artboard's next version): it shows in Artboards."
    )
  },
  "design-settings": {
    about: "The design pack's settings: the model a new project starts with, a turn's spending cap.",
    help: ee("Each field is a key of the pack's config.schema; Save checks it and writes packs.settings.design.")
  }
}, de = (...e) => e.join(`
`), Nn = {
  "design-projects": {
    about: "Your design projects: pick one, or make a new one.",
    help: de(
      "Click a project to open it in the other panels.",
      "New project asks for a name (and, if you like, its model).",
      "A project is a folder in the design pack's data folder: ~/.halo/packs/.data/design/projects/<slug>/."
    )
  },
  "design-thread": {
    about: "The project's turns: what you asked and what the model did.",
    help: de(
      "Type what to make or change and press Enter (Shift+Enter: a new line).",
      "The reply streams in as the turn runs; Cancel turn stops it.",
      "Every turn saves a version of each artboard it changed.",
      "Send comments turns the open pins into one turn."
    )
  },
  "design-artboards": {
    about: "Every artboard of the project, with its versions.",
    help: de(
      "Drag a card by its title to move it; the places are saved with the project.",
      "The slider goes back through the versions; Restore makes one the newest.",
      "Critique asks a second model for notes; Contrast checks text against its background.",
      "Rename, Delete, Download; Export and Handoff are in the toolbar."
    )
  },
  "design-assets": {
    about: "Files a turn can use: logos, photos, fonts, captures.",
    help: de(
      "Add files (or drop them here) to upload them to the project's assets/.",
      "Click one to put its path in the message box.",
      "Download saves the file."
    )
  }
};
function Sn() {
  const e = u((i) => i.projects), t = u((i) => i.slug), s = u((i) => i.error), a = u((i) => i.slug && i.data ? i.data.meta : null), o = u((i) => i.busy === "model"), d = S.useResolved(""), r = S.useHelpGroup("model_select");
  return e === null ? null : /* @__PURE__ */ n.jsxs("div", { className: "dp", children: [
    /* @__PURE__ */ n.jsx("div", { className: "dp-bar", children: /* @__PURE__ */ n.jsx(h.Button, { size: "sm", variant: "primary", onClick: () => _({ kind: "new" }), "data-testid": "design-new", children: "New project" }) }),
    a && /* @__PURE__ */ n.jsx(
      S.ModelSelect,
      {
        label: `${a.name}'s model`,
        hint: r.design,
        value: a.model || "",
        onPick: (i) => void zt(i),
        busy: o,
        inherit: { label: "the default", model: (d == null ? void 0 : d.ref) || "" },
        testid: "design-project-model",
        compact: !0
      }
    ),
    s && /* @__PURE__ */ n.jsx("p", { className: "og-problems", children: s }),
    e.length ? /* @__PURE__ */ n.jsx("ul", { className: "dp-list", children: e.map((i) => /* @__PURE__ */ n.jsx("li", { children: /* @__PURE__ */ n.jsxs("button", { className: "dp-row", "aria-pressed": i.slug === t, onClick: () => i.slug !== t && void ae(i.slug), "data-testid": "design-project", children: [
      /* @__PURE__ */ n.jsx("b", { children: i.name }),
      /* @__PURE__ */ n.jsxs("span", { className: "og-chip mono", children: [
        i.artboards,
        " artboard",
        i.artboards === 1 ? "" : "s"
      ] }),
      /* @__PURE__ */ n.jsx("span", { className: "dp-model mono muted", children: i.model || "default model" })
    ] }) }, i.slug)) }) : /* @__PURE__ */ n.jsx(h.Empty, { title: "No projects yet", body: "New project makes the first one." })
  ] });
}
function Cn() {
  const e = u((s) => {
    var a;
    return ((a = s.projects) == null ? void 0 : a.length) || 0;
  }), t = u((s) => {
    var a;
    return ((a = s.data) == null ? void 0 : a.meta.name) || "";
  });
  return /* @__PURE__ */ n.jsxs("div", { className: "glance", children: [
    /* @__PURE__ */ n.jsxs("div", { className: "glance-kicker mono", children: [
      e,
      " PROJECT",
      e === 1 ? "" : "S"
    ] }),
    /* @__PURE__ */ n.jsx("div", { className: "glance-text", children: t || "none open" })
  ] });
}
function $n() {
  const e = u((s) => !!s.error), t = u((s) => {
    var a;
    return ((a = s.projects) == null ? void 0 : a.length) || 0;
  });
  return e ? "error" : t ? "idle" : "none";
}
const $e = globalThis.__haloStudioLib;
if (!$e || !$e.workspace) throw new Error("this pack module runs inside Halo Studio: no shared workspace");
const jt = $e.workspace, R = b.createStore({ started: !1, workflows: [], inputsOf: null, inputs: [], inputsError: "", renders: {}, current: "" });
function G(e) {
  return b.useStore(R, e);
}
const wt = (e) => e instanceof D.ApiError ? e.problems[0] || e.message : String(e), Xe = (e) => e.url ? Te(e.url.replace(/^_files\//, "")) : "";
function En(e) {
  var a;
  const t = e.data || {};
  if (t.pack !== De || t.kind !== "render" || !((a = t.data) != null && a.prompt_id)) return;
  const s = t.data;
  R.update((o) => ({ renders: { ...o.renders, [s.prompt_id]: { ...o.renders[s.prompt_id], ...s, at: Date.now() } } })), s.state === "done" && (b.toast(`Render ${s.prompt_id} done: ${s.text || ""}`, "done"), O()), s.state === "error" && b.toast(`Render ${s.prompt_id}: ${s.error || s.text}`, "error", 5e3);
}
async function Je(e) {
  R.update(() => ({ inputsOf: e, inputs: [], inputsError: "" }));
  try {
    const t = await D.api.get(`media/workflows/${encodeURIComponent(e.name)}/inputs`, { source: e.source });
    R.get().inputsOf === e && R.update(() => ({ inputs: t.nodes || [] }));
  } catch (t) {
    R.get().inputsOf === e && R.update(() => ({ inputsError: wt(t) }));
  }
}
function Dn() {
  R.get().started || (R.update(() => ({ started: !0 })), pe.onEvent("pack_live", En), D.api.get("media/workflows").then(
    (e) => R.update(() => ({ workflows: e.workflows || [] })),
    () => R.update(() => ({ workflows: [] }))
  ));
}
async function Tn(e, t, s, a) {
  try {
    const o = await D.api.post(`${Z}/render`, { workflow: e.name, source: e.source, set: t, project: s, artboard: a }), d = { prompt_id: o.prompt_id, state: "queued", text: `queued ${e.name}`, project: s, artboard: a, workflow: e.name, at: Date.now() };
    return R.update((r) => ({ renders: { ...r.renders, [o.prompt_id]: { ...d, ...r.renders[o.prompt_id] } }, current: o.prompt_id })), b.toast(`Render ${o.prompt_id} queued`, "info"), [];
  } catch (o) {
    return o instanceof D.ApiError && o.problems.length ? o.problems : [wt(o)];
  }
}
function On(e) {
  const t = [];
  for (const s of e)
    for (const [a, o] of Object.entries(s.keys || {}))
      t.some((d) => d.key === a) || t.push({ key: a, value: s.inputs[o] });
  return t;
}
function Rn(e, t) {
  return typeof t == "number" && /^-?\d+(\.\d+)?$/.test(e.trim()) ? Number(e) : typeof t == "boolean" ? e === "true" : e;
}
function Mn({ a: e }) {
  return e.url ? e.kind === "video" ? /* @__PURE__ */ n.jsx("video", { className: "md-thumb", src: Xe(e), controls: !0, muted: !0, preload: "metadata", "aria-label": `${e.id} v${e.version ?? ""}` }) : /* @__PURE__ */ n.jsx("img", { className: "md-thumb", src: Xe(e), alt: `${e.id} v${e.version ?? ""}` }) : null;
}
function yt({ r: e }) {
  return e ? /* @__PURE__ */ n.jsxs("div", { className: "md-progress", "data-state": e.state, children: [
    /* @__PURE__ */ n.jsx("span", { className: "og-badge mono", "data-state": e.state === "done" ? "finished" : e.state === "error" ? "stopped" : "running", children: e.state.toUpperCase() }),
    /* @__PURE__ */ n.jsx("span", { className: "mono md-progress-text", children: e.error || e.text || e.prompt_id }),
    e.state === "done" && /* @__PURE__ */ n.jsx("div", { className: "md-thumbs", children: (e.artboards || []).map((t) => /* @__PURE__ */ n.jsx(Mn, { a: t }, t.id)) })
  ] }) : null;
}
function An() {
  const e = G((m) => m.workflows), t = G((m) => m.inputsOf), s = G((m) => m.inputs), a = G((m) => m.renders[m.current]), [o, d] = f.useState({}), [r, i] = f.useState(() => c.get().slug || ""), [l, x] = f.useState("render"), [g, y] = f.useState([]), [v, k] = f.useState(!1);
  f.useEffect(() => Dn(), []), f.useEffect(() => d({}), [t]), f.useEffect(() => {
    !R.get().inputsOf && e.length && Je(e[0]);
  }, [e]);
  const T = On(s), P = s.flatMap((m) => Object.entries(m.inputs).map(([j, N]) => ({ key: `${m.node}.${j}`, value: N, label: `${m.node}.${j} (${m.title || m.class_type})` }))), E = (m, j, N = m) => /* @__PURE__ */ n.jsx(h.Field, { label: N.toUpperCase(), children: (F) => String(j ?? "").length > 60 || m === "prompt" || m === "negative" ? /* @__PURE__ */ n.jsx("textarea", { id: F, className: "input og-text", rows: 2, value: o[m] ?? String(j ?? ""), onChange: (p) => d({ ...o, [m]: p.target.value }) }) : /* @__PURE__ */ n.jsx("input", { id: F, className: "input mono", value: o[m] ?? String(j ?? ""), onChange: (p) => d({ ...o, [m]: p.target.value }) }) }, m), L = async () => {
    if (!t) return;
    const m = {}, j = new Map([...T, ...P].map((N) => [N.key, N.value]));
    for (const [N, F] of Object.entries(o)) F !== String(j.get(N) ?? "") && (m[N] = Rn(F, j.get(N)));
    k(!0), y(await Tn(t, m, r.trim(), l.trim() || "render")), k(!1);
  }, W = (m) => {
    const j = e.find((N) => `${N.source}:${N.name}` === m);
    j && Je(j);
  };
  return /* @__PURE__ */ n.jsxs("form", { className: "og-form md-render", onSubmit: (m) => (m.preventDefault(), void L()), children: [
    /* @__PURE__ */ n.jsx(h.Field, { label: "WORKFLOW", children: (m) => /* @__PURE__ */ n.jsxs("select", { id: m, className: "input mono", value: t ? `${t.source}:${t.name}` : "", onChange: (j) => W(j.target.value), children: [
      !t && /* @__PURE__ */ n.jsx("option", { value: "", children: "pick a workflow" }),
      e.map((j) => /* @__PURE__ */ n.jsxs("option", { value: `${j.source}:${j.name}`, children: [
        j.name,
        " (",
        j.source,
        ")"
      ] }, j.source + j.name))
    ] }) }),
    T.map((m) => E(m.key, m.value)),
    P.length > 0 && /* @__PURE__ */ n.jsxs("details", { className: "md-support", children: [
      /* @__PURE__ */ n.jsxs("summary", { className: "mono", children: [
        "every node input · ",
        P.length
      ] }),
      /* @__PURE__ */ n.jsx("div", { className: "md-all", children: P.map((m) => E(m.key, m.value, m.label)) })
    ] }),
    /* @__PURE__ */ n.jsxs("div", { className: "og-form-row", children: [
      /* @__PURE__ */ n.jsx(h.Field, { label: "DESIGN PROJECT", hint: "a project's slug (the open one by default)", children: (m) => /* @__PURE__ */ n.jsx("input", { id: m, className: "input mono", value: r, onChange: (j) => i(j.target.value) }) }),
      /* @__PURE__ */ n.jsx(h.Field, { label: "ARTBOARD", children: (m) => /* @__PURE__ */ n.jsx("input", { id: m, className: "input mono", value: l, onChange: (j) => x(j.target.value) }) })
    ] }),
    g.length > 0 && /* @__PURE__ */ n.jsx("ul", { className: "og-problems", role: "alert", children: g.map((m) => /* @__PURE__ */ n.jsx("li", { children: m }, m)) }),
    /* @__PURE__ */ n.jsx("div", { className: "og-actions", children: /* @__PURE__ */ n.jsx(h.Button, { variant: "primary", type: "submit", disabled: v || !t || !r.trim(), title: r.trim() ? "Queue the render on ComfyUI" : "Name the design project first", children: "Render" }) }),
    /* @__PURE__ */ n.jsx(yt, { r: a })
  ] });
}
function Pn() {
  const e = G((s) => s.renders[s.current]), t = G((s) => Object.keys(s.renders).length);
  return e ? /* @__PURE__ */ n.jsxs("div", { className: "glance", children: [
    /* @__PURE__ */ n.jsxs("div", { className: "glance-numbers", children: [
      /* @__PURE__ */ n.jsx(S.Metric, { value: e.state, label: e.workflow || "render", tone: e.state === "done" ? "ok" : e.state === "error" ? "bad" : "accent" }),
      /* @__PURE__ */ n.jsx(S.Metric, { value: t, label: "renders here" })
    ] }),
    /* @__PURE__ */ n.jsx(yt, { r: e })
  ] }) : /* @__PURE__ */ n.jsxs("div", { className: "glance", children: [
    /* @__PURE__ */ n.jsx("div", { className: "glance-kicker mono", children: "RENDER" }),
    /* @__PURE__ */ n.jsx("div", { className: "glance-text", children: "Queue a ComfyUI workflow into a design project." }),
    /* @__PURE__ */ n.jsx("div", { className: "glance-hint", children: "Expand to pick the workflow and its inputs." })
  ] });
}
function _n() {
  const e = G((t) => t.renders[t.current]);
  return e ? e.state === "queued" || e.state === "progress" ? "working" : e.state === "error" ? "error" : jt.settle(e.at, 1600) : "none";
}
const Ee = /^(#[0-9a-fA-F]{3,8}|(rgb|rgba|hsl|hsla|oklch)\([^)]*\))$/, Ze = (e, t) => e + "\0" + t;
function zn(e, t, s, a) {
  const o = { ...e };
  return s === a ? delete o[t] : o[t] = s, o;
}
function Ln() {
  const e = u((o) => o.busy === "sync"), [t, s] = f.useState(""), a = () => void Yt(t).then((o) => o && s(""));
  return /* @__PURE__ */ n.jsxs("div", { className: "dsy-sync", children: [
    /* @__PURE__ */ n.jsx(
      "input",
      {
        className: "input mono",
        value: t,
        onChange: (o) => s(o.target.value),
        onKeyDown: (o) => o.key === "Enter" && a(),
        placeholder: "a folder path or a web page address",
        "aria-label": "Sync the design system from",
        "data-testid": "design-sync-source"
      }
    ),
    /* @__PURE__ */ n.jsx(h.Button, { size: "sm", variant: "primary", disabled: e || !t.trim(), onClick: a, "data-testid": "design-sync", children: e ? "Syncing..." : "Sync" })
  ] });
}
function In() {
  const e = u((i) => {
    var l;
    return ((l = i.data) == null ? void 0 : l.system) || null;
  }), t = u((i) => !!i.data), [s, a] = f.useState({});
  if (f.useEffect(() => a({}), [e]), !t) return /* @__PURE__ */ n.jsx(h.Empty, { title: "No project open", body: "Pick one in Projects: its design system shows here." });
  const o = Object.entries((e == null ? void 0 : e.tokens) || {}), d = ((e == null ? void 0 : e.components) || []).map((i) => typeof i == "string" ? i : (i == null ? void 0 : i.name) || "").filter(Boolean), r = Object.keys(s).length;
  return /* @__PURE__ */ n.jsxs("div", { className: "dsy", children: [
    /* @__PURE__ */ n.jsx(Ln, {}),
    !o.length && /* @__PURE__ */ n.jsx("p", { className: "muted dsy-empty", children: "No design system yet. Sync one from a codebase or a web page above, or ask for tokens in a turn." }),
    o.map(([i, l]) => /* @__PURE__ */ n.jsxs("section", { className: "dsy-group", children: [
      /* @__PURE__ */ n.jsxs("div", { className: "dsy-head mono", children: [
        /* @__PURE__ */ n.jsx("span", { children: i }),
        /* @__PURE__ */ n.jsx("span", { className: "muted", children: Object.keys(l).length })
      ] }),
      Object.entries(l).map(([x, g]) => {
        const y = s[Ze(i, x)] ?? String(g);
        return /* @__PURE__ */ n.jsxs("div", { className: "dsy-token", "data-testid": "design-token", "data-group": i, "data-name": x, children: [
          /* @__PURE__ */ n.jsx("i", { className: "dsy-swatch", "data-none": !Ee.test(y.trim()) || void 0, style: Ee.test(y.trim()) ? { background: y.trim() } : void 0 }),
          /* @__PURE__ */ n.jsx("code", { className: "mono", children: x }),
          /* @__PURE__ */ n.jsx(
            "input",
            {
              className: "input mono",
              value: y,
              "aria-label": `${i} ${x}`,
              onChange: (v) => a((k) => zn(k, Ze(i, x), v.target.value, String(g)))
            }
          )
        ] }, x);
      })
    ] }, i)),
    o.length > 0 && /* @__PURE__ */ n.jsxs("div", { className: "dsy-save", children: [
      /* @__PURE__ */ n.jsx("span", { className: "muted", children: r ? `${r} change(s)` : "edit a value to change it" }),
      /* @__PURE__ */ n.jsx("span", { className: "spacer" }),
      r > 0 && /* @__PURE__ */ n.jsx(h.Button, { size: "sm", variant: "ghost", onClick: () => a({}), children: "Undo" }),
      /* @__PURE__ */ n.jsx(h.Button, { size: "sm", variant: "primary", disabled: !r, onClick: () => void Xt(s), "data-testid": "design-tokens-save", children: "Save tokens" })
    ] }),
    d.length > 0 && /* @__PURE__ */ n.jsxs("section", { className: "dsy-group", children: [
      /* @__PURE__ */ n.jsxs("div", { className: "dsy-head mono", children: [
        /* @__PURE__ */ n.jsx("span", { children: "components" }),
        /* @__PURE__ */ n.jsx("span", { className: "muted", children: d.length })
      ] }),
      /* @__PURE__ */ n.jsx("div", { className: "dsy-chips", children: d.slice(0, 60).map((i) => /* @__PURE__ */ n.jsx("span", { className: "og-chip mono", children: i }, i)) })
    ] }),
    ((e == null ? void 0 : e.sources) || []).length > 0 && /* @__PURE__ */ n.jsxs("section", { className: "dsy-group", children: [
      /* @__PURE__ */ n.jsx("div", { className: "dsy-head mono", children: /* @__PURE__ */ n.jsx("span", { children: "sources" }) }),
      ((e == null ? void 0 : e.sources) || []).map((i) => /* @__PURE__ */ n.jsx("div", { className: "mono muted dsy-src", children: i }, i))
    ] })
  ] });
}
function Bn() {
  const e = u((a) => {
    var o;
    return ((o = a.data) == null ? void 0 : o.system) || null;
  }), t = Object.values((e == null ? void 0 : e.tokens) || {}), s = Object.values((e == null ? void 0 : e.tokens) || {}).flatMap((a) => Object.values(a)).filter((a) => Ee.test(String(a).trim())).slice(0, 8);
  return /* @__PURE__ */ n.jsxs("div", { className: "glance", children: [
    /* @__PURE__ */ n.jsxs("div", { className: "glance-numbers", children: [
      /* @__PURE__ */ n.jsx(S.Metric, { value: t.length, label: "groups" }),
      /* @__PURE__ */ n.jsx(S.Metric, { value: t.reduce((a, o) => a + Object.keys(o).length, 0), label: "tokens" })
    ] }),
    s.length > 0 && /* @__PURE__ */ n.jsx("div", { className: "dsy-chips", children: s.map((a, o) => /* @__PURE__ */ n.jsx("i", { className: "dsy-swatch", style: { background: String(a).trim() } }, o)) })
  ] });
}
function Fn() {
  const e = u((s) => s.busy === "sync"), t = u((s) => {
    var a, o;
    return Object.keys(((o = (a = s.data) == null ? void 0 : a.system) == null ? void 0 : o.tokens) || {}).length > 0;
  });
  return e ? "working" : t ? "idle" : "none";
}
function kt({ text: e }) {
  return /* @__PURE__ */ n.jsxs("div", { className: "dt-msg", "data-who": "you", children: [
    /* @__PURE__ */ n.jsx("div", { className: "dt-who mono", children: "YOU" }),
    /* @__PURE__ */ n.jsx(S.Markdown, { text: e, className: "dt-body" })
  ] });
}
function Hn(e) {
  const t = [];
  return e.tool_calls != null && t.push(`${e.tool_calls} tool call${e.tool_calls === 1 ? "" : "s"}`), e.elapsed != null && t.push(`${Math.round(Number(e.elapsed) || 0)} s`), t.push(J(e.cost)), t.push(ne(e.versions) || "no artboard changed"), e.cancelled ? t.push("cancelled") : e.code && t.push(`exit ${e.code}`), t.join(" · ");
}
const Un = f.memo(function({ h: t, n: s }) {
  var d;
  const a = t.app === "comfyui", o = ((d = t.text) == null ? void 0 : d.trim()) || (a ? `A ComfyUI render into ${(t.artboards || []).join(", ") || "the project"}.` : ne(t.versions) ? `Changed ${ne(t.versions)}.` : "No artboard changed.");
  return /* @__PURE__ */ n.jsxs("section", { className: "dt-turn", "data-testid": "design-turn", "data-n": s, "data-failed": !!t.code && !t.cancelled || void 0, children: [
    /* @__PURE__ */ n.jsx(kt, { text: t.prompt || (a ? "(a render from the Media panels)" : "(no prompt)") }),
    /* @__PURE__ */ n.jsxs("div", { className: "dt-msg", "data-who": "model", children: [
      /* @__PURE__ */ n.jsx("div", { className: "dt-who mono", children: a ? "COMFYUI" : (t.model || "MODEL").toUpperCase() }),
      /* @__PURE__ */ n.jsx(S.Markdown, { text: o, className: "dt-body" }),
      /* @__PURE__ */ n.jsxs("div", { className: "dt-meta mono muted", children: [
        t.ts ? t.ts.replace("T", " ") + " · " : "",
        Hn(t)
      ] })
    ] })
  ] });
});
function Gn(e) {
  var s;
  const t = [];
  for (const a of e)
    if (!(!a || a.type !== "assistant")) {
      for (const o of ((s = a.message) == null ? void 0 : s.content) || [])
        if (o.type === "text" && o.text) {
          const d = t[t.length - 1];
          d && d.kind === "text" ? d.text += `

` + o.text : t.push({ kind: "text", text: o.text });
        } else if (o.type === "tool_use") {
          const d = o.input_line ?? JSON.stringify(o.input ?? {});
          t.push({ kind: "tool", name: o.name || "tool", line: String(d).slice(0, 160) });
        }
    }
  return t;
}
function Wn({ t: e }) {
  const t = Gn(e.events), s = [...e.events].reverse().find((a) => a && (a.total_cost_usd != null || a.cost_usd != null));
  return /* @__PURE__ */ n.jsxs("section", { className: "dt-turn", "data-testid": "design-turn", "data-live": !e.done || void 0, children: [
    /* @__PURE__ */ n.jsx(kt, { text: e.prompt }),
    /* @__PURE__ */ n.jsxs("div", { className: "dt-msg", "data-who": "model", "aria-live": "polite", children: [
      /* @__PURE__ */ n.jsxs("div", { className: "dt-who mono", children: [
        e.label ? e.label.toUpperCase() : "MODEL",
        e.done ? "" : " · WORKING"
      ] }),
      t.map(
        (a, o) => a.kind === "text" ? /* @__PURE__ */ n.jsx(S.Markdown, { text: a.text, className: "dt-body" }, o) : /* @__PURE__ */ n.jsxs("div", { className: "dt-tool mono", "data-testid": "design-tool", children: [
          /* @__PURE__ */ n.jsx(h.Icon, { name: h.toolIcon(a.name) }),
          /* @__PURE__ */ n.jsx("b", { children: a.name }),
          /* @__PURE__ */ n.jsx("span", { className: "muted", children: a.line })
        ] }, o)
      ),
      !e.done && /* @__PURE__ */ n.jsxs("div", { className: "dt-working mono muted", children: [
        /* @__PURE__ */ n.jsxs("span", { className: "dt-dots", "aria-hidden": "true", children: [
          /* @__PURE__ */ n.jsx("i", {}),
          /* @__PURE__ */ n.jsx("i", {}),
          /* @__PURE__ */ n.jsx("i", {})
        ] }),
        " working",
        s ? " · " + J(s.total_cost_usd ?? s.cost_usd) : ""
      ] }),
      e.done && e.result && /* @__PURE__ */ n.jsxs("div", { className: "dt-meta mono muted", children: [
        e.result.cancelled ? "cancelled" : `exit ${e.result.code}`,
        " · ",
        J(e.result.cost),
        " · ",
        ne(e.result.versions) || "no artboard changed"
      ] })
    ] })
  ] });
}
const Kn = [
  "A landing page hero for a developer tool: a bold headline, one sentence, two buttons and a product screenshot area.",
  "A pricing section with three tiers, the middle one highlighted, using the design system's colours.",
  "A mobile onboarding flow of three screens as one prototype, with knobs for spacing and the accent colour."
];
function qn() {
  const e = u((g) => g.draft), t = u(z), s = u((g) => g.busy), a = u((g) => g.focusSend), o = u((g) => {
    var y;
    return (((y = g.data) == null ? void 0 : y.comments) || []).filter((v) => !v.resolved).length;
  }), d = u((g) => g.sel), [r, i] = f.useState(""), l = f.useRef(null);
  f.useEffect(() => {
    var g;
    a && ((g = l.current) == null || g.focus());
  }, [a]);
  const x = () => void ge();
  return /* @__PURE__ */ n.jsxs("div", { className: "dt-send", children: [
    /* @__PURE__ */ n.jsx(
      "textarea",
      {
        ref: l,
        className: "input dt-input",
        rows: 3,
        value: e,
        "data-testid": "design-send-box",
        onChange: (g) => c.update(() => ({ draft: g.target.value })),
        onKeyDown: (g) => {
          g.key === "Enter" && !g.shiftKey && !g.nativeEvent.isComposing && (g.preventDefault(), x());
        },
        placeholder: t ? "A turn runs: write the next message meanwhile" : "Describe what to make or change. Enter sends, Shift+Enter adds a line.",
        "aria-label": "Message to the design model"
      }
    ),
    /* @__PURE__ */ n.jsxs("div", { className: "dt-send-row", children: [
      o > 0 && /* @__PURE__ */ n.jsxs(h.Button, { size: "sm", variant: "ghost", disabled: t, onClick: () => void mt(), children: [
        "Send comments (",
        o,
        ")"
      ] }),
      /* @__PURE__ */ n.jsx("span", { className: "spacer" }),
      !t && /* @__PURE__ */ n.jsxs("span", { className: "dt-dirs", children: [
        /* @__PURE__ */ n.jsx(
          "input",
          {
            className: "input mono",
            value: r,
            maxLength: 24,
            onChange: (g) => i(g.target.value),
            placeholder: d || "direction",
            "aria-label": "Name the directions after",
            title: `The directions become ${ft(r || d)}-a, -b and -c`,
            "data-testid": "design-directions-base"
          }
        ),
        /* @__PURE__ */ n.jsx(h.Button, { size: "sm", disabled: !e.trim() || s === "send", onClick: () => void xt(r), title: "Three clearly different directions of this message, each its own artboard", "data-testid": "design-directions", children: "3 directions" })
      ] }),
      t ? /* @__PURE__ */ n.jsx(h.Button, { size: "sm", variant: "danger", disabled: s === "cancel", onClick: () => void pt(), "data-testid": "design-cancel", children: "Cancel turn" }) : /* @__PURE__ */ n.jsx(h.Button, { size: "sm", variant: "primary", kbd: "Enter", disabled: !e.trim() || s === "send", onClick: x, "data-testid": "design-send", children: "Send" })
    ] })
  ] });
}
function Vn() {
  const e = u((i) => i.data), t = u((i) => i.turn), s = u((i) => i.loading), a = f.useRef(null), o = f.useRef(!0), d = (e == null ? void 0 : e.history) || [], r = (t == null ? void 0 : t.events.length) || 0;
  return f.useLayoutEffect(() => {
    const i = a.current;
    i && o.current && (i.scrollTop = i.scrollHeight);
  }, [d.length, r, t == null ? void 0 : t.done]), e ? /* @__PURE__ */ n.jsxs("div", { className: "dt", "data-testid": "design-thread-list", children: [
    /* @__PURE__ */ n.jsxs("div", { className: "dt-head mono muted", children: [
      e.meta.name,
      " · ",
      d.length,
      " turn",
      d.length === 1 ? "" : "s",
      " · ",
      J(Ae(d)),
      " · model ",
      e.meta.model || "(default)"
    ] }),
    /* @__PURE__ */ n.jsxs("div", { className: "dt-list", ref: a, onScroll: (i) => {
      const l = i.currentTarget;
      o.current = l.scrollTop + l.clientHeight >= l.scrollHeight - 24;
    }, children: [
      d.map((i, l) => /* @__PURE__ */ n.jsx(Un, { h: i, n: l + 1 }, (i.ts || "") + l)),
      t && /* @__PURE__ */ n.jsx(Wn, { t }),
      !d.length && !t && /* @__PURE__ */ n.jsxs("div", { className: "dt-try", children: [
        /* @__PURE__ */ n.jsx("p", { className: "muted", children: "Nothing asked yet. Start from one of these, or write your own below:" }),
        Kn.map((i) => /* @__PURE__ */ n.jsx("button", { className: "dt-sugg", onClick: () => c.update((l) => ({ draft: i, focusSend: l.focusSend + 1 })), children: i }, i))
      ] })
    ] }),
    /* @__PURE__ */ n.jsx(qn, {})
  ] }) : s ? /* @__PURE__ */ n.jsx("div", { className: "og-wait mono muted", children: "opening the project..." }) : /* @__PURE__ */ n.jsx(h.Empty, { title: "No project open", body: "Pick one in Projects, or make a new one." });
}
function Yn() {
  const e = u((a) => {
    var o;
    return ((o = a.data) == null ? void 0 : o.history.length) || 0;
  }), t = u((a) => {
    var o;
    return Ae(((o = a.data) == null ? void 0 : o.history) || []);
  }), s = u(z);
  return /* @__PURE__ */ n.jsxs("div", { className: "glance", children: [
    /* @__PURE__ */ n.jsxs("div", { className: "glance-numbers", children: [
      /* @__PURE__ */ n.jsx(S.Metric, { value: e, label: "turns" }),
      /* @__PURE__ */ n.jsx(S.Metric, { value: J(t), label: "spent" }),
      /* @__PURE__ */ n.jsx(S.Metric, { value: s ? "yes" : "no", label: "running", tone: s ? "accent" : void 0 })
    ] }),
    /* @__PURE__ */ n.jsx("div", { className: "glance-hint", children: "Expand for the thread and the message box." })
  ] });
}
function Xn() {
  const e = u(z), t = u((a) => {
    var o, d;
    return !!((o = a.turn) != null && o.done) && !!((d = a.turn.result) != null && d.code) && !a.turn.result.cancelled;
  }), s = u((a) => !!a.data);
  return t ? "error" : e ? "working" : s ? "idle" : "none";
}
function H(e) {
  return () => (f.useEffect(() => (en(), _e()), []), e());
}
function Jn() {
  return /* @__PURE__ */ n.jsx(S.PackForm, { p: { pack: De } });
}
function Zn() {
  return /* @__PURE__ */ n.jsx("div", { className: "glance", children: /* @__PURE__ */ n.jsx("div", { className: "glance-text", children: "The model a new project starts with, a turn's cap." }) });
}
const U = (e, t) => ({ id: e, testid: e, ...Nn[e], ...kn[e], ...t }), Qn = [
  U("design-projects", { title: "Projects", x: 0, y: 0, w: 5, h: 22, minW: 4, minH: 12, face: "detail", glance: Cn, detail: Sn, useMotion: H($n) }),
  U("design-system", { title: "Design system", x: 0, y: 22, w: 5, h: 34, minW: 4, minH: 12, face: "detail", glance: Bn, detail: In, useMotion: H(Fn) }),
  U("design-assets", { title: "Assets", x: 0, y: 56, w: 5, h: 0, minW: 4, minH: 12, face: "detail", glance: wn, detail: jn, useMotion: H(() => "none") }),
  U("design-artboards", { title: "Artboards", primary: !0, x: 5, y: 0, w: 12, h: 0, minW: 8, minH: 24, face: "detail", glance: bn, detail: fn, settings: gn, useMotion: H(vn) }),
  U("design-thread", { title: "Thread", x: 17, y: 0, w: 7, h: 0, minW: 5, minH: 24, face: "detail", glance: Yn, detail: Vn, useMotion: H(Xn) }),
  U("design-render", { title: "Render", x: 0, y: 200, w: 12, h: 40, minW: 6, minH: 12, face: "detail", collapsed: !0, glance: Pn, detail: An, useMotion: H(_n) }),
  U("design-settings", { title: "Settings", x: 12, y: 200, w: 12, h: 24, minW: 6, minH: 10, face: "detail", collapsed: !0, glance: Zn, detail: Jn, useMotion: H(() => "none") })
], es = [["folder", "Folder (a shareable site)"], ["html", "HTML"], ["png", "PNG"], ["svg", "SVG"], ["pdf", "PDF"]];
function ts() {
  const [e, t] = f.useState(""), [s, a] = f.useState(""), o = u((l) => l.busy === "new"), d = S.useResolved(""), r = S.useHelpGroup("model_select"), i = () => void ut(e, s.trim());
  return /* @__PURE__ */ n.jsxs(
    h.Dialog,
    {
      open: !0,
      onClose: $,
      title: "New design project",
      kicker: "DESIGN · PROJECT",
      testid: "design-new-dialog",
      footer: /* @__PURE__ */ n.jsxs(n.Fragment, { children: [
        /* @__PURE__ */ n.jsx(h.Button, { onClick: $, children: "Cancel" }),
        /* @__PURE__ */ n.jsx(h.Button, { variant: "primary", disabled: !e.trim() || o, onClick: i, "data-testid": "design-new-go", children: "Create project" })
      ] }),
      children: [
        /* @__PURE__ */ n.jsxs("label", { className: "fd-field", children: [
          /* @__PURE__ */ n.jsx("span", { className: "rail-label mono", children: "NAME" }),
          /* @__PURE__ */ n.jsx("input", { className: "input", value: e, maxLength: 60, onChange: (l) => t(l.target.value), onKeyDown: (l) => l.key === "Enter" && i(), placeholder: "Launch page", "data-testid": "design-new-name" })
        ] }),
        /* @__PURE__ */ n.jsx(
          S.ModelSelect,
          {
            label: "MODEL (OPTIONAL)",
            hint: r.design,
            value: s,
            onPick: a,
            testid: "design-new-model",
            inline: !0,
            inherit: { label: "the default", model: (d == null ? void 0 : d.ref) || "" }
          }
        ),
        /* @__PURE__ */ n.jsx("p", { className: "muted", children: "A folder under ~/.halo/packs/.data/design/projects/; every turn in it saves a version of the artboards it changed." })
      ]
    }
  );
}
function ns({ aid: e }) {
  const t = u((d) => Re(d, e)), [s, a] = f.useState((t == null ? void 0 : t.title) || e), o = () => s.trim() && void Ft(e, s.trim());
  return /* @__PURE__ */ n.jsxs(
    h.Dialog,
    {
      open: !0,
      onClose: $,
      title: `Rename ${(t == null ? void 0 : t.title) || e}`,
      kicker: "DESIGN · ARTBOARD",
      testid: "design-rename-dialog",
      footer: /* @__PURE__ */ n.jsxs(n.Fragment, { children: [
        /* @__PURE__ */ n.jsx(h.Button, { onClick: $, children: "Cancel" }),
        /* @__PURE__ */ n.jsx(h.Button, { variant: "primary", disabled: !s.trim(), onClick: o, "data-testid": "design-rename-go", children: "Rename" })
      ] }),
      children: [
        /* @__PURE__ */ n.jsx("input", { className: "input", value: s, maxLength: 80, onChange: (d) => a(d.target.value), onKeyDown: (d) => d.key === "Enter" && o(), "aria-label": "New name", "data-testid": "design-rename-name" }),
        /* @__PURE__ */ n.jsxs("p", { className: "muted", children: [
          "The title changes; the artboard's id (",
          e,
          "), its files and its versions stay."
        ] })
      ]
    }
  );
}
function ss({ aid: e }) {
  const t = u((s) => Re(s, e));
  return /* @__PURE__ */ n.jsx(
    h.Dialog,
    {
      open: !0,
      onClose: $,
      title: `Delete ${(t == null ? void 0 : t.title) || e}?`,
      kicker: "DESIGN · ARTBOARD",
      testid: "design-delete-dialog",
      footer: /* @__PURE__ */ n.jsxs(n.Fragment, { children: [
        /* @__PURE__ */ n.jsx(h.Button, { onClick: $, children: "Cancel" }),
        /* @__PURE__ */ n.jsx(h.Button, { variant: "danger", onClick: () => void Ht(e), "data-testid": "design-delete-yes", children: "Delete it" })
      ] }),
      children: /* @__PURE__ */ n.jsxs("p", { children: [
        "Its files and all ",
        (t == null ? void 0 : t.versions.length) || 0,
        " version(s) go from the project folder; its open pins are resolved. Export it first to keep a copy."
      ] })
    }
  );
}
function as() {
  const e = u((r) => {
    var i;
    return ((i = r.data) == null ? void 0 : i.artboards) || [];
  }), t = u((r) => r.busy === "export"), [s, a] = f.useState("folder"), [o, d] = f.useState("");
  return /* @__PURE__ */ n.jsxs(
    h.Dialog,
    {
      open: !0,
      onClose: $,
      title: "Export",
      kicker: "DESIGN · EXPORT",
      testid: "design-export-dialog",
      footer: /* @__PURE__ */ n.jsxs(n.Fragment, { children: [
        /* @__PURE__ */ n.jsx(h.Button, { onClick: $, children: "Cancel" }),
        /* @__PURE__ */ n.jsx(h.Button, { variant: "primary", disabled: t, onClick: () => void Ut(s, o), "data-testid": "design-export-go", children: "Export" })
      ] }),
      children: [
        /* @__PURE__ */ n.jsx("div", { className: "ow-list", role: "radiogroup", "aria-label": "Export as", children: es.map(([r, i]) => /* @__PURE__ */ n.jsxs("label", { className: "check od-pick", children: [
          /* @__PURE__ */ n.jsx("input", { type: "radio", name: "design-export", checked: s === r, onChange: () => a(r) }),
          " ",
          i
        ] }, r)) }),
        /* @__PURE__ */ n.jsxs("label", { className: "fd-field", children: [
          /* @__PURE__ */ n.jsx("span", { className: "rail-label mono", children: "ARTBOARD" }),
          /* @__PURE__ */ n.jsxs("select", { className: "input", value: o, onChange: (r) => d(r.target.value), children: [
            /* @__PURE__ */ n.jsx("option", { value: "", children: "All artboards" }),
            e.map((r) => /* @__PURE__ */ n.jsx("option", { value: r.id, children: r.title || r.id }, r.id))
          ] })
        ] })
      ]
    }
  );
}
function Qe(e) {
  var t;
  (t = navigator.clipboard) == null || t.writeText(e).then(() => b.toast("Copied", "done"), () => b.toast("Copy it by hand: the clipboard is off here", "info"));
}
function os({ d: e }) {
  const t = (s) => s.aa ? "ok" : s.aa_large ? "warn" : "bad";
  return /* @__PURE__ */ n.jsx(h.Dialog, { open: !0, onClose: $, title: `Contrast of ${e.aid}`, kicker: "DESIGN · WCAG", testid: "design-contrast", footer: /* @__PURE__ */ n.jsx(h.Button, { onClick: $, children: "Close" }), children: e.error ? /* @__PURE__ */ n.jsx("p", { className: "og-problems", children: e.error }) : e.data ? /* @__PURE__ */ n.jsxs(n.Fragment, { children: [
    e.data.pairs.length > 0 && /* @__PURE__ */ n.jsxs("table", { className: "dd-contrast mono", children: [
      /* @__PURE__ */ n.jsx("thead", { children: /* @__PURE__ */ n.jsxs("tr", { children: [
        /* @__PURE__ */ n.jsx("th", {}),
        /* @__PURE__ */ n.jsx("th", { children: "text" }),
        /* @__PURE__ */ n.jsx("th", { children: "on" }),
        /* @__PURE__ */ n.jsx("th", { children: "ratio" }),
        /* @__PURE__ */ n.jsx("th", {})
      ] }) }),
      /* @__PURE__ */ n.jsx("tbody", { children: e.data.pairs.map((s, a) => /* @__PURE__ */ n.jsxs("tr", { children: [
        /* @__PURE__ */ n.jsx("td", { children: /* @__PURE__ */ n.jsx("i", { className: "dd-dot", "data-tone": t(s) }) }),
        /* @__PURE__ */ n.jsx("td", { children: s.fg }),
        /* @__PURE__ */ n.jsx("td", { children: s.bg }),
        /* @__PURE__ */ n.jsx("td", { children: s.ratio.toFixed(2) }),
        /* @__PURE__ */ n.jsx("td", { children: s.aaa ? "AAA" : s.aa ? "AA" : s.aa_large ? "large" : "fail" })
      ] }, a)) })
    ] }),
    /* @__PURE__ */ n.jsx("p", { className: "muted", children: e.data.note })
  ] }) : /* @__PURE__ */ n.jsx("p", { className: "muted", children: "checking..." }) });
}
function rs({ d: e }) {
  return /* @__PURE__ */ n.jsxs(
    h.Dialog,
    {
      open: !0,
      onClose: $,
      title: `Design system: ${e.tokens} token${e.tokens === 1 ? "" : "s"}`,
      kicker: "DESIGN · SYNC",
      testid: "design-sync-dialog",
      footer: /* @__PURE__ */ n.jsx(h.Button, { variant: "primary", onClick: $, children: "Done" }),
      children: [
        /* @__PURE__ */ n.jsxs("p", { children: [
          "Read from ",
          /* @__PURE__ */ n.jsx("code", { className: "mono", children: e.source }),
          " and merged into the project's system.json; the next turn designs with it."
        ] }),
        e.groups.length ? /* @__PURE__ */ n.jsxs("table", { className: "dd-contrast mono", children: [
          /* @__PURE__ */ n.jsx("thead", { children: /* @__PURE__ */ n.jsxs("tr", { children: [
            /* @__PURE__ */ n.jsx("th", { children: "group" }),
            /* @__PURE__ */ n.jsx("th", { children: "tokens" })
          ] }) }),
          /* @__PURE__ */ n.jsx("tbody", { children: e.groups.map(([t, s]) => /* @__PURE__ */ n.jsxs("tr", { children: [
            /* @__PURE__ */ n.jsx("td", { children: t }),
            /* @__PURE__ */ n.jsx("td", { children: s })
          ] }, t)) })
        ] }) : /* @__PURE__ */ n.jsx("p", { className: "muted", children: "No tokens were found there." }),
        e.sources.length > 0 && /* @__PURE__ */ n.jsx("pre", { className: "dd-lines mono", children: e.sources.join(`
`) })
      ]
    }
  );
}
function is() {
  const e = u((s) => s.dialog);
  if (!e) return null;
  if (e.kind === "new") return /* @__PURE__ */ n.jsx(ts, {});
  if (e.kind === "rename") return /* @__PURE__ */ n.jsx(ns, { aid: e.aid });
  if (e.kind === "delete") return /* @__PURE__ */ n.jsx(ss, { aid: e.aid });
  if (e.kind === "export") return /* @__PURE__ */ n.jsx(as, {});
  if (e.kind === "contrast") return /* @__PURE__ */ n.jsx(os, { d: e });
  if (e.kind === "synced") return /* @__PURE__ */ n.jsx(rs, { d: e });
  if (e.kind === "exported")
    return /* @__PURE__ */ n.jsx(h.Dialog, { open: !0, onClose: $, title: `Exported: ${e.as}`, kicker: "DESIGN · EXPORT", testid: "design-exported", footer: /* @__PURE__ */ n.jsx(h.Button, { variant: "primary", onClick: $, children: "Done" }), children: /* @__PURE__ */ n.jsx("pre", { className: "dd-lines mono", children: e.lines.join(`
`) || "nothing was written" }) });
  const t = `halo --cwd "${e.path}" "continue from HANDOFF.md"`;
  return /* @__PURE__ */ n.jsxs(
    h.Dialog,
    {
      open: !0,
      onClose: $,
      title: "Handoff bundle written",
      kicker: "DESIGN · HANDOFF",
      testid: "design-handoff-dialog",
      footer: /* @__PURE__ */ n.jsxs(n.Fragment, { children: [
        /* @__PURE__ */ n.jsx(h.Button, { onClick: () => Qe(e.path), children: "Copy the path" }),
        /* @__PURE__ */ n.jsx(h.Button, { variant: "primary", onClick: $, children: "Done" })
      ] }),
      children: [
        /* @__PURE__ */ n.jsx("p", { children: "The artboards, the design system and HANDOFF.md for the next Halo or Claude Code session:" }),
        /* @__PURE__ */ n.jsx("pre", { className: "dd-lines mono", "data-testid": "design-handoff-path", children: e.path }),
        /* @__PURE__ */ n.jsxs("p", { className: "muted", children: [
          "Continue there with ",
          /* @__PURE__ */ n.jsx("code", { className: "mono", children: t })
        ] }),
        /* @__PURE__ */ n.jsx(h.Button, { size: "sm", variant: "ghost", onClick: () => Qe(t), children: "Copy the command" })
      ]
    }
  );
}
function ds() {
  const e = yn;
  f.useEffect(() => {
    const r = window.setInterval(() => {
      document.hidden || b.studio.get().section !== V || me().then((i) => i[0] && ae(i[0].slug));
    }, 4e3);
    return () => window.clearInterval(r);
  }, []);
  const [t, s] = f.useState(""), a = u((r) => r.busy === "new"), o = u((r) => r.error), d = () => void ut(t);
  return /* @__PURE__ */ n.jsx("div", { className: "fl-start ds-start", "data-testid": "design-start", children: /* @__PURE__ */ n.jsxs("div", { className: "fl-start-inner", children: [
    /* @__PURE__ */ n.jsxs("header", { className: "fl-start-head", children: [
      /* @__PURE__ */ n.jsx("div", { className: "glance-kicker mono", children: "DESIGN · ON YOUR OWN APPS" }),
      /* @__PURE__ */ n.jsx("h1", { className: "fl-start-title", children: "Design, on your own apps" }),
      /* @__PURE__ */ n.jsx("p", { className: "muted", children: e.what })
    ] }),
    /* @__PURE__ */ n.jsxs("div", { className: "fl-start-grid", children: [
      /* @__PURE__ */ n.jsxs(h.Surface, { className: "fl-start-form", motion: "idle", children: [
        /* @__PURE__ */ n.jsxs("label", { className: "fd-field", children: [
          /* @__PURE__ */ n.jsx("span", { className: "rail-label mono", children: "NAME YOUR FIRST PROJECT" }),
          /* @__PURE__ */ n.jsx(
            "input",
            {
              className: "input",
              value: t,
              maxLength: 60,
              onChange: (r) => s(r.target.value),
              onKeyDown: (r) => r.key === "Enter" && d(),
              placeholder: "Launch page",
              "data-testid": "design-start-name"
            }
          )
        ] }),
        /* @__PURE__ */ n.jsx("div", { className: "ds-go", children: /* @__PURE__ */ n.jsx(h.Button, { variant: "primary", disabled: !t.trim() || a, onClick: d, "data-testid": "design-start-create", children: "Create project" }) }),
        o && /* @__PURE__ */ n.jsxs("p", { className: "og-problems", children: [
          "Studio could not read the projects: ",
          o
        ] })
      ] }),
      /* @__PURE__ */ n.jsx("aside", { className: "fl-start-side", children: /* @__PURE__ */ n.jsx("ol", { className: "fl-explain", children: e.steps.map(([r, i], l) => /* @__PURE__ */ n.jsxs("li", { children: [
        /* @__PURE__ */ n.jsx("span", { className: "fl-explain-n mono", children: l + 1 }),
        /* @__PURE__ */ n.jsxs("span", { children: [
          /* @__PURE__ */ n.jsx("b", { children: r }),
          /* @__PURE__ */ n.jsx("span", { className: "fl-explain-text", children: i })
        ] })
      ] }, r)) }) })
    ] })
  ] }) });
}
function ls({ specs: e }) {
  f.useEffect(() => _e(), []);
  const t = u((a) => a.projects !== null), s = u(Dt);
  return t ? s ? /* @__PURE__ */ n.jsx(ds, {}) : /* @__PURE__ */ n.jsx(jt.Workspace, { section: V, specs: e }) : /* @__PURE__ */ n.jsx("div", { className: "fl-start", children: /* @__PURE__ */ n.jsx("div", { className: "og-wait mono muted", children: "reading the design projects..." }) });
}
const cs = ".dt{height:100%;display:grid;grid-template-rows:auto minmax(0,1fr) auto;gap:8px}.dt-head{font-size:11px;white-space:nowrap;overflow:hidden;text-overflow:ellipsis}.dt-list{overflow:auto;min-height:0;display:grid;gap:14px;align-content:start;padding-right:4px}.dt-turn{display:grid;gap:6px;animation:rise var(--t-slow) var(--ease)}.dt-msg{display:grid;gap:4px;padding:8px 11px;border-radius:var(--radius);font-size:13px;max-width:94%;min-width:0}.dt-msg[data-who=you]{justify-self:end;background:var(--warn-soft);border:1px solid color-mix(in srgb,var(--warn) 30%,transparent)}.dt-msg[data-who=model]{justify-self:start;background:var(--surface-2);border:1px solid var(--line);border-left:2px solid var(--accent)}.dt-turn[data-failed] .dt-msg[data-who=model]{border-left-color:var(--bad)}.dt-turn[data-live] .dt-msg[data-who=model]{box-shadow:0 0 18px var(--accent-soft)}.dt-who{font-size:9.5px;letter-spacing:.1em;color:var(--muted)}.dt-msg[data-who=you] .dt-who{color:var(--warn);text-align:right}.dt-meta{font-size:10.5px;padding-top:2px;border-top:1px solid var(--line)}.dt-tool{display:flex;align-items:center;gap:6px;font-size:11px;padding:3px 8px;border-radius:99px;border:1px solid var(--line);background:var(--bg-2);min-width:0}.dt-tool b{color:var(--accent);font-weight:600}.dt-tool span{overflow:hidden;text-overflow:ellipsis;white-space:nowrap}.dt-working{display:flex;align-items:center;gap:8px;font-size:11px}.dt-dots{display:inline-flex;gap:3px}.dt-dots i{width:5px;height:5px;border-radius:50%;background:var(--accent);animation:fp-pulse 1.2s var(--ease) infinite}.dt-dots i:nth-child(2){animation-delay:.2s}.dt-dots i:nth-child(3){animation-delay:.4s}.dt-send{display:grid;gap:6px;padding-top:8px;border-top:1px solid var(--line)}.dt-input{resize:vertical;min-height:58px;font:inherit;font-size:13px}.dt-send-row{display:flex;align-items:center;gap:8px}.dt-try{display:grid;gap:6px}.dt-try p{margin:0;font-size:12.5px}.dt-sugg{text-align:left;padding:8px 10px;font:inherit;font-size:12.5px;color:var(--text);border:1px solid var(--line);border-radius:var(--radius-sm);background:var(--bg-2);cursor:pointer}.dt-sugg:hover{border-color:var(--accent);background:var(--accent-soft)}.md{display:grid;gap:6px;min-width:0;overflow-wrap:anywhere;line-height:1.5}.md-p{margin:0}.md-h{font-weight:700;margin-top:2px}.md-h1{font-size:15px}.md-h2{font-size:14px}.md-h3,.md-h4{font-size:13px;color:var(--accent);letter-spacing:.02em}.md-list{margin:0;padding-left:20px;display:grid;gap:2px}.md-pre{margin:0;padding:8px 10px;font:11.5px/1.45 var(--mono);border-radius:var(--radius-sm);background:var(--bg);border:1px solid var(--line);overflow:auto;white-space:pre}.md-code{font:11.5px var(--mono);padding:0 4px;border-radius:4px;background:var(--bg-2);border:1px solid var(--line)}.md-quote{margin:0;padding:2px 10px;border-left:2px solid var(--line-strong);color:var(--muted)}.md-link{color:var(--accent)}.md-img{font-style:italic}", us = ".dp{display:grid;gap:10px;align-content:start}.dp-list{list-style:none;margin:0;padding:0;display:grid;gap:3px}.dp-row{width:100%;display:grid;grid-template-columns:minmax(0,1fr) auto;gap:2px 8px;text-align:left;padding:7px 9px;font:inherit;font-size:13px;border:1px solid transparent;border-radius:var(--radius-sm);background:none;color:var(--text);cursor:pointer}.dp-row:hover{background:var(--accent-soft)}.dp-row[aria-pressed=true]{border-color:var(--accent);background:var(--accent-soft)}.dp-row b{overflow:hidden;text-overflow:ellipsis;white-space:nowrap}.dp-model{grid-column:1 / -1;font-size:11px;overflow:hidden;text-overflow:ellipsis;white-space:nowrap}.da{height:100%;display:grid;grid-template-rows:auto minmax(0,1fr);gap:8px}.da-bar{display:flex;align-items:center;gap:8px;flex-wrap:wrap;font-size:12px}.da-bar .segmented button{padding:3px 10px;font-size:12px}.da-scroll{overflow:auto;min-height:0;border:1px solid var(--line);border-radius:var(--radius-sm);background-color:var(--bg-2);background-image:radial-gradient(var(--grid-line) 1px,transparent 1px);background-size:20px 20px}.da-world{position:relative;transform-origin:0 0}.da-card{position:absolute;display:grid;gap:8px;padding:10px 12px;border-radius:var(--radius);background:var(--surface);border:1px solid var(--line-strong);box-shadow:var(--glow);transition:border-color var(--t) var(--ease),box-shadow var(--t) var(--ease)}.da-card[data-selected]{border-color:var(--accent);box-shadow:var(--glow-strong)}.da-card[data-dragging]{z-index:3;opacity:.94}.da-title{display:flex;align-items:center;gap:6px;cursor:grab;-webkit-user-select:none;user-select:none;touch-action:none;font-size:13px;min-width:0}.da-card[data-dragging] .da-title{cursor:grabbing}.da-title b{overflow:hidden;text-overflow:ellipsis;white-space:nowrap}.da-title .og-chip{cursor:default}.da-title .og-chip[data-app]{color:var(--accent);border-color:color-mix(in srgb,var(--accent) 45%,transparent)}.da-frame{position:relative;margin-inline:auto;border-radius:var(--radius-sm);border:1px solid var(--line);background:var(--bg);min-height:60px;box-sizing:content-box}.da-scaler{overflow:hidden;position:relative;border-radius:inherit}.da-scaler iframe{border:0;transform-origin:0 0;background:var(--surface);pointer-events:none}.da-card[data-selected] .da-scaler iframe{pointer-events:auto}.da-img{display:block;width:100%;height:auto;max-height:240px;object-fit:contain}.da-link{display:grid;gap:4px;padding:18px;color:var(--accent);text-decoration:none;font-size:13px}.da-nofile{padding:24px;text-align:center;font-size:12px}.da-pin{position:absolute;transform:translate(-50%,-50%);width:20px;height:20px;border-radius:50%;display:grid;place-items:center;font:700 10.5px var(--mono);color:var(--accent-ink);background:var(--warn);box-shadow:0 0 0 2px var(--surface),0 0 10px var(--warn);cursor:pointer;border:0;padding:0;z-index:2}.da-pin[aria-expanded=true]{outline:2px solid var(--accent);outline-offset:2px}.da-pin[data-crit]{background:var(--accent-2);box-shadow:0 0 0 2px var(--surface),0 0 10px var(--accent-2)}.da-foot{display:grid;gap:6px;font-size:11.5px}.da-versions{display:grid;grid-template-columns:minmax(0,1fr) auto auto;align-items:center;gap:8px}.da-versions input[type=range]{accent-color:var(--accent);width:100%}.da-actions{display:flex;flex-wrap:wrap;gap:2px}.da-actions .btn{padding-inline:8px}.das{display:grid;gap:10px;align-content:start;min-height:100%;border-radius:var(--radius-sm);transition:background var(--t) var(--ease)}.das[data-over]{background:var(--accent-soft);outline:1px dashed var(--accent);outline-offset:-4px}.das-bar{display:flex;align-items:center;gap:8px}.das-hint{font-size:12px}.das-list{list-style:none;margin:0;padding:0;display:grid;gap:3px}.das-row{display:grid;grid-template-columns:minmax(0,1fr) auto;align-items:center;gap:6px}.das-pick{display:grid;grid-template-columns:28px minmax(0,1fr) auto;align-items:center;gap:8px;padding:4px 6px;text-align:left;font:inherit;font-size:12.5px;border:1px solid transparent;border-radius:var(--radius-sm);background:none;color:var(--text);cursor:pointer}.das-pick:hover{background:var(--accent-soft)}.das-pick img{width:28px;height:28px;object-fit:cover;border-radius:4px;border:1px solid var(--line)}.das-kind{font-size:9px;font-style:normal;color:var(--muted);text-transform:uppercase;text-align:center}.das-name{overflow:hidden;text-overflow:ellipsis;white-space:nowrap}.das-empty{margin:0;font-size:12.5px}.dd-lines{margin:0;padding:10px 12px;max-height:260px;overflow:auto;font-size:11.5px;white-space:pre-wrap;overflow-wrap:anywhere;border-radius:var(--radius-sm);background:var(--bg);border:1px solid var(--line)}.dd-contrast{width:100%;border-collapse:collapse;font-size:12px}.dd-contrast th{text-align:left;color:var(--muted);font-weight:500;padding:4px 6px;border-bottom:1px solid var(--line)}.dd-contrast td{padding:4px 6px;border-bottom:1px solid var(--line)}.dd-dot{display:inline-block;width:9px;height:9px;border-radius:50%;background:var(--faint)}.dd-dot[data-tone=ok]{background:var(--ok)}.dd-dot[data-tone=warn]{background:var(--warn)}.dd-dot[data-tone=bad]{background:var(--bad)}.ds-go{margin-top:14px}.da-device{width:auto;padding:3px 8px;font-size:12px}.da-overlay{position:absolute;top:0;right:0;bottom:0;left:0;z-index:1;cursor:crosshair;border-radius:inherit;background:color-mix(in srgb,var(--accent) 6%,transparent);outline:1px dashed color-mix(in srgb,var(--accent) 55%,transparent);outline-offset:-3px}.da-scroll[data-tool=comment] .da-frame{border-color:var(--accent)}.da-pop{position:absolute;z-index:4;width:240px;display:grid;gap:6px;padding:8px;margin:12px 0 0 8px;font-size:12px;border-radius:var(--radius-sm);background:var(--surface-glass);border:1px solid var(--accent);box-shadow:var(--glow-strong);-webkit-backdrop-filter:blur(var(--blur));backdrop-filter:blur(var(--blur))}.da-pop textarea{resize:vertical;min-height:0;font-size:12.5px}.da-pop-row{display:flex;align-items:center;gap:4px;justify-content:flex-end;font-size:10.5px}.da-pop-head{display:flex;align-items:center;gap:6px;font-size:10.5px;letter-spacing:.04em;text-transform:uppercase}.da-pop-head .icon-btn{width:20px;height:20px;font-size:11px}.da-pop-text{margin:0;white-space:pre-wrap;overflow-wrap:anywhere;color:var(--text)}.da-edit{width:auto;max-width:340px;margin:-6px 0 0 -6px}.dk{display:grid;gap:10px}.dk-ver{display:flex;align-items:center;gap:8px;flex-wrap:wrap;font-size:11.5px}.dk-ver .og-chip{color:var(--accent);border-color:var(--accent)}.dk-row{display:grid;gap:4px;padding:8px 10px;border:1px solid var(--line);border-radius:var(--radius-sm);background:var(--bg-2)}.dk-head{display:flex;align-items:baseline;justify-content:space-between;gap:8px;font-size:12.5px}.dk-value{color:var(--accent);font-size:11.5px}.dk-row input[type=range]{accent-color:var(--accent);width:100%}.dk-row input[type=color]{width:48px;height:26px;padding:0;border:1px solid var(--line-strong);border-radius:var(--radius-sm);background:none;cursor:pointer}.dk-target{font-size:10.5px}.dsy{display:grid;gap:10px;align-content:start}.dsy-sync{display:grid;grid-template-columns:minmax(0,1fr) auto;gap:6px}.dsy-sync .input{font-size:12px;padding:4px 8px}.dsy-empty{margin:0;font-size:12.5px}.dsy-group{display:grid;gap:3px}.dsy-head{display:flex;justify-content:space-between;font-size:10.5px;letter-spacing:.08em;text-transform:uppercase;color:var(--accent);padding-bottom:3px;border-bottom:1px solid var(--line)}.dsy-token{display:grid;grid-template-columns:14px minmax(0,1fr) minmax(0,1.1fr);align-items:center;gap:6px;font-size:11.5px}.dsy-token code{overflow:hidden;text-overflow:ellipsis;white-space:nowrap;color:var(--muted)}.dsy-token .input{padding:2px 6px;font-size:11.5px}.dsy-swatch{display:inline-block;width:14px;height:14px;border-radius:4px;border:1px solid var(--line-strong)}.dsy-swatch[data-none]{border-style:dashed;background:none}.dsy-save{display:flex;align-items:center;gap:6px;font-size:11.5px}.dsy-chips{display:flex;flex-wrap:wrap;gap:4px}.dsy-chips .og-chip{cursor:default}.dsy-src{font-size:11px;overflow-wrap:anywhere}.dt-dirs{display:inline-flex;align-items:center;gap:4px}.dt-dirs .input{width:92px;padding:3px 6px;font-size:11.5px}";
function ps(e, t) {
  const s = t.lib.css(us + `
` + cs), a = t.lib.commands(() => Jt().map(({ id: d, label: r, hint: i, run: l }) => ({ id: d, label: r, hint: i, run: l })));
  e.classList.add("ds-page");
  const o = Nt.createRoot(e);
  return o.render(
    /* @__PURE__ */ n.jsxs(n.Fragment, { children: [
      /* @__PURE__ */ n.jsx(ls, { specs: Qn }),
      /* @__PURE__ */ n.jsx(is, {})
    ] })
  ), () => {
    o.unmount(), a(), s();
  };
}
export {
  ps as mount
};
