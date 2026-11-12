"""MSK3 (#772): MSK2's follow-up (decision of Jonathan, 12/11 evening: « Oui, comme la CLI ») — no message
of the Discord bot nor of the webhook shows a subscription's id: the commands to copy name the VM by the
CLI's rule, the card's texts, what a button ran and its output, the notices and the webhook's messages
are masked at the display; the buttons' arguments and the stores keep the full id. M5020–M5029,
measured by tests/unit/test_bot_masking.py.

The form of a lot's file, as scripts/mutation_check.py loads it: MUTANTS, TESTS (its own ids),
optionally TESTS_ALSO and CONTROL; its paths as plain strings.
"""
BOT = "glorfindel/bot.py"
NOTICES = "glorfindel/vm_notices.py"
ESC = "glorfindel/escalations.py"
_M = "tests/unit/test_bot_masking.py"

MUTANTS = [
    ("M5020", "the bot's commands to copy give the full id: « glorfindel restore /subscriptions/… » pasted "
     "from the channel (MSK3)", BOT,
     '    rid = _vm_for_a_command(esc["resource_id"])\n',
     '    rid = esc["resource_id"]\n'),
    ("M5021", "the bot names the VM of a command by hand: a name two VMs hold, or a homonym's, in a "
     "« restore … --yes » (MSK3)", BOT,
     "    return _name_for_a_command(resource_id)\n",
     '    return resource_id.rstrip("/").rsplit("/", 1)[-1]\n'),
    ("M5022", "the card's embed says the model's explanation and the reason raw: the signal's id they "
     "copied, in the channel (MSK3)", BOT,
     "    no subscription's id in it (MSK3, `_shown`).\"\"\"\n    esc = _shown(esc)\n",
     "    no subscription's id in it (MSK3, `_shown`).\"\"\"\n    esc = dict(esc)\n"),
    ("M5023", "the card's suggested steps shown as the model wrote them: « glorfindel restore "
     "/subscriptions/… » on the card (MSK3)", BOT,
     '        out["suggested_steps"] = [masking.ids_masked(str(x), subscriptions=subs) for x in out["suggested_steps"]]\n',
     '        out["suggested_steps"] = list(out["suggested_steps"])\n'),
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
     "                f\"> {webhook_text(ids_masked(esc['reason'], subscriptions=subs)[:500])}\\n\"\n",
     "                f\"> {webhook_text(esc['reason'][:500])}\\n\"\n"),
    ("M5029", "an autonomous action's announcement by the webhook says the model's explanation raw (MSK3)",
     ESC,
     '        f"> {webhook_text(ids_masked(explanation[:800], subscriptions=subs))}\\n"\n',
     '        f"> {webhook_text(explanation[:800])}\\n"\n'),
]
TESTS = {
    "M5020": f"{_M}::test_the_command_to_copy_names_the_vm_by_its_name",
    "M5021": f"{_M}::test_the_command_never_names_a_homonym",
    "M5022": f"{_M}::test_the_card_shows_no_subscription_and_the_store_keeps_it",
    "M5023": f"{_M}::test_the_card_shows_no_subscription_and_the_store_keeps_it",
    "M5024": f"{_M}::test_an_identity_plan_s_command_is_shown_whole_or_held",
    "M5025": f"{_M}::test_what_a_button_ran_is_said_without_the_subscription",
    "M5026": f"{_M}::test_what_a_button_ran_is_said_without_the_subscription",
    "M5027": f"{_M}::test_a_notice_is_said_without_the_subscription_and_kept_whole",
    "M5028": f"{_M}::test_an_escalation_by_the_webhook_says_no_subscription",
    "M5029": f"{_M}::test_an_action_s_announcement_by_the_webhook_says_no_subscription",
}
