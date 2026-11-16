"""tests.helpers.crew_map_script -- the builder's scripted model on the Map tab (Halo 3.6.0.0 R3), called by
crew_rig.scripted for a request it does not know. Each request is a list of tool calls made one per round (the next
when the last one's TOOL line is in the text), then a reply.

    "send anything touching auth to my-reviewer after the code workflow"   map_box_add + map_line_add (code -> it, says auth)
    "make me a reviewer agent and hand reviews to it"                       agent_make + map_box_add + map_line_add
    "what is my map" / "show me my workflows" / "why did reviewer run"      studio_show (map / lists / run), no change
    "loop it back"                                                           a line that would make a circle: refused
    "use ship-it" / "use starter"                                            map_use
"""

from __future__ import annotations

REVIEWER = {"name": "my-reviewer", "does": "Reviews a change; one line per problem.", "uses": ["read", "bash"],
            "careful": "ask-changes"}


def reviewer_calls(map_name: "str | None" = "starter") -> list:
    """The three calls of "make me a reviewer agent and hand reviews to it" (the session parity test sends the same);
    `map_name` None: no `map` (the map open on the tab, in Studio's builder box)."""
    on = {"map": map_name} if map_name else {}
    return [{"tool": "agent_make", "args": dict(REVIEWER)},
            {"tool": "map_box_add", "args": {**on, "kind": "agent", "ref": "my-reviewer"}},
            {"tool": "map_line_add", "args": {**on, "from": "main", "to": "my-reviewer", "when": {"says": ["review"]}}}]


PLANS = {
    "send anything touching auth": [{"tool": "map_box_add", "args": {"kind": "agent", "ref": "my-reviewer"}},
                                    {"tool": "map_line_add", "args": {"from": "code", "to": "my-reviewer", "when": {"says": ["auth"]}}}],
    "make me a reviewer agent": reviewer_calls(None),  # the tab's map (3.6.0.2: parity-map in the parity test)
    "what is my map": [{"tool": "studio_show", "args": {"what": "map"}}],
    "show me my workflows": [{"tool": "studio_show", "args": {"what": "lists"}}],
    "why did reviewer run": [{"tool": "studio_show", "args": {"what": "run", "name": "reviewer"}}],
    "loop it back": [{"tool": "map_line_add", "args": {"from": "review", "to": "plan", "when": "always"}}],
    "use ship-it": [{"tool": "map_use", "args": {"map": "ship-it"}}],
    "use starter": [{"tool": "map_use", "args": {"map": "starter"}}],
}


def map_turn(req: str, user: str) -> "dict | None":
    for key, calls in PLANS.items():
        if key not in req:
            continue
        done = user.count("\n\nTOOL ")
        if done < len(calls):
            return calls[done]
        last = user.rsplit("\n\nTOOL ", 1)[-1]
        return {"reply": "From the map: " + last.split(":\n", 1)[-1][:3000]}
    return None
