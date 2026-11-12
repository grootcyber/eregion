"""MSK3 (#772): MSK2's follow-up (decision of Jonathan, 12/11 evening: « Oui, comme la CLI ») — no message
of the Discord bot nor of the webhook shows a subscription's id: the commands to copy name the VM by the
CLI's rule, the card's texts, what a button ran and its output, the notices and the webhook's messages
are masked at the display; the buttons' arguments and the stores keep the full id. M5020–M5029,
then M5098–M5104 after the first review (the commands name the VM by `<groupe>/<nom>`, resolved by
the CLI on its own host or refused; the CLI reads the VM back before acting; a thread named before
MSK3; the announcement cut before its masking), M5110–M5113 after the second (snapshot resolves the
form, a subscription only a command named, a VM's own id, a group the shell reads), measured by
tests/unit/test_bot_masking.py.

The form of a lot's file, as scripts/mutation_check.py loads it: MUTANTS, TESTS (its own ids),
optionally TESTS_ALSO and CONTROL; its paths as plain strings.
"""
BOT = "glorfindel/bot.py"
NOTICES = "glorfindel/vm_notices.py"
ESC = "glorfindel/escalations.py"
CLI = "glorfindel/cli.py"
MASK = "glorfindel/masking.py"
_M = "tests/unit/test_bot_masking.py"

MUTANTS = [
    ("M5020", "the bot's commands to copy give the full id: « glorfindel restore /subscriptions/… » pasted "
     "from the channel (MSK3)", BOT,
     '    rid = _vm_for_a_command(esc["resource_id"])\n',
     '    rid = esc["resource_id"]\n'),
    ("M5021", "the bot names the VM of a command by its name alone: pasted on a terminal that knows only a "
     "homonym of another group, « restore vm-01 --yes » restores the homonym (MSK3)", BOT,
     "    return masking.group_and_name(resource_id)\n",
     '    return str(resource_id).rstrip("/").rsplit("/", 1)[-1]\n'),
    ("M5022", "the card's embed says the model's explanation and the reason raw: the signal's id they "
     "copied, in the channel (MSK3)", BOT,
     "    no subscription's id in it (MSK3, `_shown`).\"\"\"\n    esc = _shown(esc)\n",
     "    no subscription's id in it (MSK3, `_shown`).\"\"\"\n    esc = dict(esc)\n"),
    ("M5023", "the card's suggested steps shown as the model wrote them: « glorfindel restore "
     "/subscriptions/… » on the card (MSK3)", BOT,
     '        out["suggested_steps"] = [masking.ids_masked(str(x), subscriptions=subs) for x in steps]\n',
     '        out["suggested_steps"] = list(steps)\n'),
    ("M5024", "a plan's command masked in place: « az … --ids vm (groupe rg) » shown as a command no one "
     "can paste (MSK3)", BOT,
     "            return _COMMAND_HELD         # a command is shown whole or not at all, never altered\n",
     "            return masked\n"),
    ("M5025", "what a button ran said with its arguments: « → glorfindel revert /subscriptions/… --yes » in "
     "the thread (MSK3)", BOT,
     '        cmd_display = "glorfindel " + _args_said(self.cli_args)\n',
     '        cmd_display = "glorfindel " + " ".join(self.cli_args)\n'),
    ("M5026", "a command's output posted raw in the thread: Azure's « over scope '/subscriptions/…' » "
     "(MSK3)", BOT,
     '        short = _masked(output.strip(), esc)[:1800].replace("`", "ˋ") or "(pas de sortie)"\n',
     '        short = output.strip()[:1800].replace("`", "ˋ") or "(pas de sortie)"\n'),
    ("M5027", "a notice posted in the VM's thread as the store keeps it: the id its text names, in the "
     "channel — and in the fallback's Discord message (MSK3)", NOTICES,
     "    from glorfindel.chat_text import discord_code, discord_text\n    notice = _shown(notice)\n",
     "    from glorfindel.chat_text import discord_code, discord_text\n"),
    ("M5028", "an escalation by the webhook says the model's reason raw: the signal's id in the channel "
     "(MSK3)", ESC,
     "                f\"> {webhook_text(masked(esc['reason'], rid, subs)[:500])}\\n\"\n",
     "                f\"> {webhook_text(esc['reason'][:500])}\\n\"\n"),
    ("M5029", "an autonomous action's announcement by the webhook says the model's explanation raw (MSK3)",
     ESC,
     '        f"> {webhook_text(shown(explanation)[:800])}\\n"\n',
     '        f"> {webhook_text(explanation[:800])}\\n"\n'),
    # The review of MSK3 (r1).
    ("M5098", "the CLI passes a `<groupe>/<nom>` its host does not know to Azure as it is, never refused "
     "(MSK3)", CLI,
     "    if pair is not None and not found:\n",
     "    if False:\n"),
    ("M5099", "the CLI reads `<groupe>/<nom>` by its name alone: the bot's command, pasted where only a "
     "homonym of another group is known, takes the homonym (MSK3)", CLI,
     " and (pair is None or _group_of(key) == group):\n",
     ":\n"),
    ("M5100", "the CLI does not know `<groupe>/<nom>`: the bot's commands passed to Azure as an id (MSK3)",
     CLI,
     '    if len(parts) == 2 and all(p.strip() for p in parts) and parts[0].lower() != "subscriptions":\n',
     "    if False:\n"),
    ("M5101", "glorfindel reset --yes acts without reading back the VM it resolved (MSK3)", CLI,
     "    _say_vm(resource_id)                        # read back before anything, --yes too (MSK3)\n",
     ""),
    ("M5102", "a step the code wrote shown with the card's short name or its id masked: a homonym's "
     "command, or no command (MSK3)", BOT,
     '        steps = [masking.commands_named(str(x), rid) for x in out["suggested_steps"]]\n',
     '        steps = list(out["suggested_steps"])\n'),
    ("M5103", "a thread opened before MSK3 keeps the subscription's id in its name at every post (MSK3)",
     BOT,
     "                    await _renamed_if_it_names_a_subscription(thread, resource_id, vm_name)\n",
     ""),
    ("M5104", "the announcement's text cut mid-GUID in the notices' store: its first digits pass the "
     "masking in the VM's thread (MSK3)", ESC,
     "cut(explanation, 800),", "explanation[:800],"),
    # The review of MSK3 (r2).
    ("M5110", "glorfindel snapshot takes `<groupe>/<nom>` as an id: the card's step fails on Azure (MSK3)", CLI,
     "    resource_id = _resolve_resource_id(resource_id)\n    vault, vault_rg, _ = _backup_vault_from_config(vault)\n",
     "    vault, vault_rg, _ = _backup_vault_from_config(vault)\n"),
    ("M5111", "the subscriptions learned from the text once rewritten: a bare id of one only a command's id "
     "named passes in the webhook and the notices (MSK3)", MASK,
     '    subs = set(subscriptions or ()) | subscriptions_known(text) | subscriptions_known(str(resource_id or ""))\n',
     '    subs = set(subscriptions or ()) | subscriptions_known(str(resource_id or ""))\n'),
    ("M5112", "the last segment of any id taken for a VM's name: an extension's id gives « rg/ext » (MSK3)", MASK,
     '    if "resourcegroups" in low[:-1] and len(low) >= 2 and low[-2] == "virtualmachines":\n',
     '    if "resourcegroups" in low[:-1] and "providers" in low:\n'),
    ("M5113", "a group with « ( ) » left bare in the command: the shell refuses it (MSK3)", MASK,
     '            return shlex.quote(f"{parts[i + 1]}/{parts[-1]}")\n',
     '            return f"{parts[i + 1]}/{parts[-1]}"\n'),
]
TESTS = {
    "M5020": f"{_M}::test_the_command_to_copy_names_the_vm_by_its_group_and_name",
    "M5021": f"{_M}::test_the_command_to_copy_names_the_vm_by_its_group_and_name",
    "M5022": f"{_M}::test_the_card_shows_no_subscription_and_the_store_keeps_it",
    "M5023": f"{_M}::test_the_card_shows_no_subscription_and_the_store_keeps_it",
    "M5024": f"{_M}::test_an_identity_plan_s_command_is_shown_whole_or_held",
    "M5025": f"{_M}::test_what_a_button_ran_is_said_without_the_subscription",
    "M5026": f"{_M}::test_what_a_button_ran_is_said_without_the_subscription",
    "M5027": f"{_M}::test_a_notice_is_said_without_the_subscription_and_kept_whole",
    "M5028": f"{_M}::test_an_escalation_by_the_webhook_says_no_subscription",
    "M5029": f"{_M}::test_an_action_s_announcement_by_the_webhook_says_no_subscription",
    "M5098": f"{_M}::test_the_group_and_name_form_is_resolved_on_its_host",
    "M5099": f"{_M}::test_the_bot_s_command_pasted_on_a_host_that_knows_only_the_homonym_is_refused",
    "M5100": f"{_M}::test_the_group_and_name_form_is_resolved_on_its_host",
    "M5101": f"{_M}::test_the_cli_says_the_vm_it_resolved_before_acting_yes_too",
    "M5102": f"{_M}::test_a_step_s_command_names_the_vm_by_its_group_and_name",
    "M5103": f"{_M}::test_the_reused_thread_is_renamed_before_the_post",
    "M5104": f"{_M}::test_the_announcement_is_masked_then_cut_never_a_guid_s_first_characters",
    "M5110": f"{_M}::test_the_snapshot_step_of_a_card_acts_on_the_vm_it_names",
    "M5111": f"{_M}::test_a_subscription_only_a_command_named_is_masked_bare_too",
    "M5112": f"{_M}::test_only_a_vm_s_own_id_is_named_by_its_group_and_name",
    "M5113": f"{_M}::test_a_group_the_shell_would_read_is_quoted",
}
