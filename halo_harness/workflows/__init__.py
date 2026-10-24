"""halo_harness.workflows -- a pack's declarative workflows on top of the
Orchestra (Halo 3.2.0.0 R5, docs/WORKFLOWS.md).

A workflow file (`<pack>/workflows/<name>.yaml`; its shape schemas/workflow_yaml.py,
its meaning packs/workflow_rules.py) COMPILES to an Orchestra goal, its
hand-offs and a pinned plan (compile.py), and the existing pipeline
(orchestra/run.py) runs it: there is no second engine. The modules here are
the hooks the pipeline calls when a goal carries a `workflow`:

    spec.py      find and read a workflow (`<pack>/<name>`) of a pack that runs here
    inputs.py    the typed inputs (text, path, json, artifact:<schema>) and the prerequisites
    compile.py   workflow + inputs -> Goal (what, done_when, test, budget, files, lineup, plan, handoffs, workflow)
    pinned.py    the lead's split as a pinned plan: the lead may refine the briefs, never the stages
    runtime.py   a lane's stage: its brief in the prompt, its run-time `when`, its timeout and budget
    gate.py      the gate widened: typed artifacts against their schemas, the evidence, each stage's test
    outputs.py   the run's outputs: copied to <run>/artifacts/<name>/ and listed in the report
    cli.py       `halo workflow list | show | check | run`
    goal.py      `--as goal`: the compiled run queued for the supervisor
"""
