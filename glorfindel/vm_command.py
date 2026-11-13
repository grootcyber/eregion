"""What a command to copy names a VM by: « <groupe>/<nom> » (MSK3, #772; MSK3b, #787).

A command Glorfindel writes for a human to run — a card's step or reason, the TUI's line, a hint of
the CLI — is copied: to another terminal (an operator's, whose discovery may know only a homonym of
another group), or on a subscription where two groups each hold a VM of that name. Its name alone
could take the other VM there, `--yes` asking nothing; its full id names the subscription (MSK2).
`glorfindel` resolves `<groupe>/<nom>` on its own host, the group AND the name matching, or refuses
(glorfindel/cli.py, `_resolve_resource_id`) — never another VM.

No masking here: the card keeps its full id in `resource_id`, the signal and the journals too. This
is how the code writes its own commands, at the source — the graph and the watch call it, which may
not import the display's masking (tests/unit/test_cli_masking.py). glorfindel/masking.py reads the
same rule back (`commands_named`) for what was written before.
"""
from __future__ import annotations

import shlex

UNNAMED = "<id: glorfindel list --ids>"


def group_and_name(resource_id) -> str:
    """« <groupe>/<nom> » of a VM's own ARM id (« …/virtualMachines/<nom> »), quoted for the shell
    when its group holds a character of it (Azure allows « ( ) »): the command is pasted as it is.
    Never a child of a VM (an extension) nor another resource (a NSG): the command would name
    another resource. An id with no group, a short name: « <id: glorfindel list --ids> »."""
    parts = str(resource_id or "").strip().rstrip("/").split("/")
    low = [p.lower() for p in parts]
    if "resourcegroups" in low[:-1] and len(low) >= 2 and low[-2] == "virtualmachines":
        i = low.index("resourcegroups")
        if i + 1 < len(parts) - 1 and parts[i + 1] and parts[-1]:
            return shlex.quote(f"{parts[i + 1]}/{parts[-1]}")
    return UNNAMED
