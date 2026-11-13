"""MSK3b (#787): every command to copy Glorfindel writes for a VM names it by `<groupe>/<nom>` (the card
« exécutée », the TUI, the CLI's hints and the steps of a card it shows, the watch's cards, the console's
📋 Command), which the CLI resolves — never its name alone, which could take a VM of that name in another
group. M5125–M5134, then M5180–M5182 after the first review, measured by tests/unit/test_vm_command.py (two VMs « web » in two groups)."""
AGENT = "glorfindel/agent.py"
TUI = "glorfindel/tui.py"
CLI = "glorfindel/cli.py"
REASSERT = "glorfindel/reassert.py"
READINESS = "glorfindel/readiness.py"
RECOVERY = "glorfindel/recovery_watch.py"
CONSOLE_JS = "eregion_console/static/glorfindel.js"
MASK = "glorfindel/masking.py"
_T = "tests/unit/test_vm_command.py"

MUTANTS = [
    ("M5125", "the card « exécutée » undoes its VM by its name alone again: `release web --yes` copied to a "
     "terminal that knows only the homonym of another group lifts that one's quarantine (MSK3b)", AGENT,
     "    vm = group_and_name(rid)\n",
     '    vm = rid.rstrip("/").rsplit("/", 1)[-1]\n'),
    ("M5126", "the TUI's line names the VM by its name alone: `restore web --yes` restores a homonym (MSK3b)", TUI,
     '        vm_arg = group_and_name(e["resource_id"])\n',
     "        vm_arg = vm_short\n"),
    ("M5127", "the CLI's hints name the VM by its name alone: the command copied elsewhere takes a homonym "
     "(MSK3b)", CLI,
     '        return UNNAMED\n    return named\n',
     '        return UNNAMED\n    return _short_name(resource_id)\n'),
    ("M5128", "the CLI gives `<groupe>/<nom>` that takes, here, the VM of another subscription (MSK3b, MSK2's "
     "rule)", CLI,
     '    if resolved.rstrip("/").lower() != str(resource_id or "").rstrip("/").lower():\n'
     '        return UNNAMED\n    return named\n',
     "    return named\n"),
    ("M5129", "`pending` shows a card's own steps as written: a short name of a homonym, or a full id masked "
     "into no command (MSK3b)", CLI,
     '            step = _shown(str(step), e["resource_id"])\n',
     "            step = _ids_masked(str(step))\n"),
    ("M5130", "the TTL card's step names the VM by its full id: masked, « web (groupe …) » is no command "
     "(MSK3b)", REASSERT,
     'f"Lever : glorfindel release {group_and_name(rid)} --yes"',
     'f"Lever : glorfindel release {rid} --yes"'),
    ("M5131", "the readiness card's `activate` names the VM by its name alone (MSK3b)", READINESS,
     "`glorfindel activate {group_and_name(rid)}`.",
     "`glorfindel activate {vm}`."),
    ("M5132", "a recovery card's `release` names the VM by its full id again (MSK3b)", RECOVERY,
     "S'il précède l'incident et que la VM est saine : glorfindel release {group_and_name(rid)} --yes",
     "S'il précède l'incident et que la VM est saine : glorfindel release {rid} --yes"),
    ("M5133", "the held snapshot's step names the VM by its full id: the subscription on the card, no "
     "command once masked (MSK3b)", AGENT,
     "f\"`glorfindel snapshot {group_and_name(signal.get('resource_id', ''))} --yes` \"",
     "f\"`glorfindel snapshot {signal.get('resource_id', '')} --yes` \""),
    ("M5134", "the console's 📋 Command undoes an action taken alone by the VM's name alone (MSK3b)", CONSOLE_JS,
     "    const vm = _vmArg(rid);\n    const ip = (esc.action_params && esc.action_params.ip) || '<ip>';\n",
     "    const vm = rid.split('/').pop();\n    const ip = (esc.action_params && esc.action_params.ip) || '<ip>';\n"),
    # Review 1 (#792): `pending` rewrote a step, then masked it by what was left — the VM's id gone, its
    # subscription was no longer learned, and a bare GUID of it further on showed.
    ("M5180", "`pending` masks a card's step once rewritten: its id gone, a bare GUID of its subscription "
     "shows when the environment names another (MSK3b, review)", CLI,
     '            step = _shown(str(step), e["resource_id"])\n',
     '            step = _ids_masked(__import__("glorfindel.masking").masking.commands_named(str(step), '
     'e["resource_id"]))\n'),
    ("M5181", "the card's id no longer teaches its subscription: a step written before MSK3b (the name "
     "alone, a bare GUID) shows the GUID (MSK3b, review)", MASK,
     '    subs = set(subscriptions or ()) | subscriptions_known(text) | subscriptions_known(str(resource_id or ""))\n',
     "    subs = set(subscriptions or ()) | subscriptions_known(text)\n"),
    ("M5182", "the `not_in_place` recovery card's `restore` names the VM by its full id (MSK3b, review: "
     "one string, the tree's guard reads it)", RECOVERY,
     "Restaurer la VM sur place depuis le poste : glorfindel restore {group_and_name(rid)} --before",
     "Restaurer la VM sur place depuis le poste : glorfindel restore {rid} --before"),
]
TESTS = {
    "M5125": f"{_T}::test_the_executed_card_s_undo_names_its_vm_by_its_group_and_name",
    "M5126": f"{_T}::test_the_tui_s_commands_name_the_vm_by_its_group_and_name",
    "M5127": f"{_T}::test_the_cli_s_hints_name_each_homonym_by_its_own_group",
    "M5128": f"{_T}::test_the_cli_asks_for_the_id_when_its_group_and_name_would_take_another_vm",
    "M5129": f"{_T}::test_the_cli_names_the_vm_of_a_card_s_own_steps_written_before",
    "M5130": f"{_T}::test_the_ttl_card_names_its_vm_by_its_group_and_name",
    "M5131": f"{_T}::test_the_readiness_card_names_activate_s_vm_by_its_group_and_name",
    "M5132": f"{_T}::test_every_command_to_copy_in_the_tree_names_its_vm_by_its_group_and_name",
    "M5133": f"{_T}::test_the_snapshot_step_of_a_held_card_names_its_vm_by_its_group_and_name",
    "M5134": f"{_T}::test_the_console_s_command_names_the_vm_by_its_group_and_name",
    "M5180": f"{_T}::test_the_cli_masks_a_card_s_step_by_the_subscriptions_it_named_before_the_rewriting",
    "M5181": f"{_T}::test_the_cli_masks_a_card_s_step_by_the_subscriptions_it_named_before_the_rewriting",
    "M5182": f"{_T}::test_every_command_to_copy_in_the_tree_names_its_vm_by_its_group_and_name",
}
