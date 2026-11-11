"""halo_harness.checks -- the checks Halo offers after setup (Halo 3.2.2.0 R2; moved here from start/ in 3.4.0.0 B,
when the guided first run became the shipped `first-run` pack). Setup's Check page in Studio, `halo check` and the
console setup read this one list; each check says what it does, what it costs, how long it takes and what it writes.

    catalog.py   CHECKS (doctor, catalog, hello, steward, gym), the order, run_one / run_many
    run.py       what each core check runs, and the cost line it states
    steward.py   the steward candidates row
    pack.py      an enabled pack's Setup check (`contributes.setup`, kind check) as one more row
    provider.py  is there a model to run on: the configured providers and the default model
"""
