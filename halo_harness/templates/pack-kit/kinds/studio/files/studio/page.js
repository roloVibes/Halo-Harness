// __NAME__'s page: a Studio section drawn whole by this ES module (docs/EXTENSION_API.md "A section's view").
// mount(el, api) gets the section's page; `api.lib` is Studio's own React, ReactDOM and parts (ui.Button,
// ui.Surface, ...), so the page looks like the rest of Studio and no second React is loaded. `api.routes` is where
// the pack's own routes answer (server/routes.py); api.lib.fetchJson reaches them (a client scoped to this pack). What
// mount returns runs when the section goes away. Studio loads it once the owner grants studio-script.
export function mount(el, api) {
  const { React, ReactDOM, ui, fetchJson } = api.lib;
  const h = React.createElement;

  function Page() {
    const [line, setLine] = React.useState("asking the pack's routes ...");
    const ask = () =>
      fetchJson(api.routes + "/ping").then(
        (r) => setLine("the routes answer: " + JSON.stringify(r)),
        (e) => setLine("the routes did not answer: " + e.message),
      );
    React.useEffect(() => void ask(), []);
    return h(
      ui.Surface,
      { className: "pk-page", motion: "idle" },
      h("h2", null, "hello from " + api.pack),
      h("p", { className: "muted", "data-testid": "kit-page-line" }, line),
      h(ui.Button, { onClick: ask }, "Ask again"),
    );
  }

  const root = ReactDOM.createRoot(el);
  root.render(h(Page));
  return () => root.unmount();
}
