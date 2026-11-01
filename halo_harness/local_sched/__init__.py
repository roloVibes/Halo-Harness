"""halo_harness.local_sched -- Halo 3.3.7.0 R3: the scheduler of a session's local models
(plans/local-model-fit-brief.md Part D1, G5, G6, G12; docs/MODELS-ollama-steward-sched.md).

    facts.py      what a host's card holds and what each model weighs at its lane's window
    swap_cost.py  how long a model takes to load: the ledger, the speed card, the weights (the source named)
    warm_set.py   which of a lineup's models co-reside on a card (bin packing) and how often one pass swaps
    pivot.py      one pivot (unload -> load) as a visible step, one at a time per card, a minimum residency
    preview.py    a lineup's swap preview and its hygiene lines (`halo teams use`, the Roles lineup tab)
    loads.py      the loading tax: the loads of a session and the seconds they took
    place.py      where each lane's model should run across the reachable hosts (`halo local place`)
    bundle_fit.py, bundle_needs.py, bundle_options.py   3.3.7.0 R5: a bundle's honest verdict and its ways out
    reserve.py, reserve_act.py, claims_file.py          3.3.7.0 R5: the reservations, claimed and released

Deterministic and model-free: arithmetic over the card, the catalog rows, the ledger and the hosts' `route`
answers. Loads go through the Ollama API (providers/ollama_load.py) or a halo host's typed operations
(host/ops_control.py); nothing here changes a server setting.
"""
