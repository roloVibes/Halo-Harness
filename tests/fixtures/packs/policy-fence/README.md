# Policy fence (a fixture pack)

The test pack of the policy hook contract (Halo 3.3.10.0, docs/EXTENSION_API.md "Policy hooks"): one
policy, `fence` (`policy/fence.py`, plain Python speaking the JSON-lines protocol), that denies a Write or Edit whose
path is outside the project folder and allows the rest, `on_error: deny`; and one mode, `fenced`, that arms it.

    halo pack install tests/fixtures/packs/policy-fence
    halo pack enable policy-fence --grant hooks
    halo pack mode policy-fence fenced on
    halo pack policy test policy-fence fence Write '{"file_path": "/tmp/x"}'
    deny -- fence: outside the project (40 ms)

From 3.3.10.0 R2 a session enforces it: a Write outside the project is refused with
`policy: deny -- fence: outside the project (pack policy-fence, rule outside-project)`, and `halo pack policy log
policy-fence` prints the verdict. A post-call request (`"after": true`, for a copy whose pack.yaml says `after: true`)
is answered pass. The tests' seams (`HALO_POLICY_TEST_*`: a slow answer, a bad line, an echo, an exit, ask instead of
deny, and after the call a redact of one word or a drop) are set by the tests only.
