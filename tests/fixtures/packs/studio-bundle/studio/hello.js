// A pack's Studio bundle (3.2.0.0 R3 fixture): an ES module whose mount(el, api)
// draws the panel. Studio calls it once the panel shows, with the panel's body
// element and the bundle panel's api (docs/EXTENSION_API.md "Studio
// contributions"): api.pack (the pack's id), api.get(path) (a file of the pack,
// as text), api.config() (its settings) and, 3.3.10.0 R3, api.publish(kind,
// data), api.on(kind, cb), api.getData(path), api.mode(), api.attention(row)
// and api.route(section, panel). One button per call, one result line each
// (data-testid bundle-<call>-result). The returned function, if any, runs when
// the panel goes away.
export function mount(el, api) {
  const made = [];
  const add = (tag, text, testid) => {
    const node = document.createElement(tag);
    if (text) node.textContent = text;
    if (testid) node.dataset.testid = testid;
    el.appendChild(node);
    made.push(node);
    return node;
  };
  const line = add("p", "hello from " + api.pack, "pack-bundle-hello");
  line.className = "pack-bundle-hello";
  add("p", "drawn by studio/hello.js").className = "muted";
  const heard = add("p", "", "bundle-on-result");
  const off = api.on("hello.said", (e) => {
    heard.textContent = "heard " + e.kind + ": " + (e.data && e.data.text);
  });
  const act = (name, label, run) => {
    const out = add("p", "", `bundle-${name}-result`);
    const b = add("button", label, `bundle-${name}`);
    b.type = "button";
    b.addEventListener("click", () => {
      out.textContent = "...";
      Promise.resolve()
        .then(run)
        .then(
          (v) => (out.textContent = typeof v === "string" ? v : JSON.stringify(v)),
          (e) => (out.textContent = "error: " + (e && e.message ? e.message : String(e))),
        );
    });
  };
  act("publish", "Publish hello.said", () => api.publish("hello.said", { text: "hi from the bundle" }).then((r) => (r.ok ? "published" : "not published")));
  act("publish-bad", "Publish an undeclared kind", () => api.publish("hello.nope", {}));
  act("getdata", "Read note.json", () => api.getData("note.json"));
  act("mode", "Read the mode", () => api.mode().then((m) => "mode " + (m.mode || "none") + (m.label ? " (" + m.label + ")" : "")));
  act("attention", "Ask for attention", () => api.attention({ row: "greet", kind: "hello.ask", what: "the bundle asks you" }).then((r) => "row " + r.row));
  act("route", "Go to Fleet", () => (api.route("fleet") ? "routed" : "no such section"));
  return () => {
    off();
    for (const n of made) n.remove();
  };
}
