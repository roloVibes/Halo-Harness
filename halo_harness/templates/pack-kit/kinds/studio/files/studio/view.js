// __NAME__'s Studio bundle panel: an ES module whose mount(el, api) draws the panel (docs/EXTENSION_API.md "The
// bundle panel's api"). Studio loads it only once the owner grants studio-script. `api.pack` is the pack's id,
// `api.getData(path)` reads a file of its data folder, `api.mode()` its runtime mode. What mount returns runs when
// the panel goes away.
export function mount(el, api) {
  const head = document.createElement("p");
  head.textContent = "hello from " + api.pack;
  const rows = document.createElement("p");
  rows.className = "muted";
  rows.textContent = "reading rows.json ...";
  el.appendChild(head);
  el.appendChild(rows);
  api
    .getData("rows.json")
    .then((text) => {
      const list = JSON.parse(text);
      rows.textContent = (Array.isArray(list) ? list.length : 0) + " row(s) in rows.json";
    })
    .catch(() => {
      rows.textContent = "no rows.json yet: the pack's code writes it in its data folder";
    });
  return () => {
    head.remove();
    rows.remove();
  };
}
