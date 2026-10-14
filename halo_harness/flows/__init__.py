"""halo_harness.flows -- Halo flows (3.0.4.0): a flow file runs an input
through agents in roles, an org, a ComfyUI render, a human confirm, posting
and metrics, with every artifact in a design project. See docs/FLOWS.md.

    spec.py        the flow file: find, load, validate_flow, refs
    state.py       the run folder, Flow (step states, events, the pump)
    gates.py       the human gate (gate file, answer file)
    run.py         run(run_dir, adapters=...) -> report
    steps_*.py     the step kinds
    adapters.py    the real model, org and ComfyUI calls
    report.py      report.json and its text form
    cli.py         `halo flow ...`
"""
