// A pack's Studio bundle (3.2.0.0 R3 fixture): an ES module whose mount(el, api)
// draws the panel. Studio calls it once the panel shows, with the panel's body
// element and a small api: api.pack (the pack's id), api.get(path) (a file of
// the pack, as text) and api.config() (its settings). The returned function,
// if any, runs when the panel goes away.
export function mount(el, api) {
  const line = document.createElement("p");
  line.className = "pack-bundle-hello";
  line.dataset.testid = "pack-bundle-hello";
  line.textContent = "hello from " + api.pack;
  el.appendChild(line);
  const note = document.createElement("p");
  note.className = "muted";
  note.textContent = "drawn by studio/hello.js";
  el.appendChild(note);
  return () => {
    line.remove();
    note.remove();
  };
}
