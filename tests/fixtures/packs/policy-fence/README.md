# Policy fence (a fixture pack)

The test pack of the policy hook contract (Halo 3.3.10.0 R1, docs/EXTENSION_API.md "Policy hooks", draft): one
policy, `fence` (`policy/fence.py`, plain Python speaking the JSON-lines protocol), that denies a Write or Edit whose
path is outside the project folder and allows the rest, `on_error: deny`; and one mode, `fenced`, that arms it.

    halo pack install tests/fixtures/packs/policy-fence
    halo pack mode policy-fence fenced on
    halo pack policy test policy-fence fence Write '{"file_path": "/tmp/x"}'
    deny -- fence: outside the project (40 ms)

Nothing enforces the verdict yet: 3.3.10.0 R2 wires it into the permission engine.
