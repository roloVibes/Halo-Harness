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

3.3.6.0 R2, the capability-filtered search (plans/local-model-fit-brief.md Part F):

    truths.py, truth_rules.py   declared / expected / verified for every capability and fit fact
    search.py                   the gates, the ranking, the verdicts; search_filters.py the fit and supply filters;
                                search_cost.py the cost preview; search_query.py the search as browse runs it
    presets.py, presets_save.py the nine presets, the sentence parser, Save as role template, the role offer
    role_gaps.py                a lineup's gaps ("find a model for this role")

Nothing here pulls or downloads a model (3.3.5.0 R3 and R4 do; Download and verify is studio/local_verify_job.py).
"""
