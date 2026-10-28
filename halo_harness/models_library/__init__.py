"""halo_harness.models_library -- Halo 3.3.5.0 R2: the library browser (docs/STUDIO-local.md "Library").

What could be installed, read from the two sites that list it, each row with a card and a fit badge per host:

    ollama_library.py   ollama.com/library (the catalog) and /library/<model>/tags (the tags), parsed from HTML
    ollama_registry.py  registry.ollama.ai's OCI manifests: the weights' and the projector's bytes, the config blob
    hf_hub.py           the Hugging Face Hub's API: GGUF and MLX repos, their files and sizes, gated and licence
    snapshot.py         snapshot_ollama.json, the shipped catalog: the offline fallback and the first paint
    cache.py            <state>/cache/models-library.json and the one fetch (providers/http.urlopen_tls)
    shapes.py           a family's shape for the memory arithmetic of a model that is not installed
    rows.py             LibraryRow, card_for_row, fit_for_row
    browse.py           the query the route (studio/models_library_api.py) and `halo models browse` share

Nothing here pulls or downloads a model (3.3.5.0 R3 and R4 do).
"""
