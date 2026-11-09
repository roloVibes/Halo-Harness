---
description: "Service pack: runs its own program with your words (no model call)"
argument-hint: "[words]"
run: ["${halo_python}", "${CLAUDE_PLUGIN_ROOT}/service/ticker.py", "--say"]
---
The service pack's entry command: it runs service/ticker.py --say with the words after it.
