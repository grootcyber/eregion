"""VP1b (#917): the remainders of VP1's review — a verdict given by hand no longer says it came from
the proposal (glorfindel/escalations.py), the pass held card by card and a card without a time zone
never proposed (glorfindel/proposed_verdict.py), the bot's signature suffix only when there is one and
the thread archived after a confirmation as after a verdict (glorfindel/bot.py). M6336–M6346, measured
by tests/unit/test_proposed_verdict.py and tests/unit/test_proposed_verdict_bot.py."""
PV = "glorfindel/proposed_verdict.py"
ESC = "glorfindel/escalations.py"
BOT = "glorfindel/bot.py"
_P = "tests/unit/test_proposed_verdict.py"
_B = "tests/unit/test_proposed_verdict_bot.py"

MUTANTS = [
    ("M6336", "a card confirmed from its proposal, then judged by hand, still says « proposed » (VP1b)", ESC,
     '    e.pop("verdict_from", None)\n',
     ""),
    ("M6337", "a card without a time zone stops the whole pass: its age compared to an aware now (VP1b)", PV,
     "    return at is not None and (at.tzinfo is None or now - at <= HORIZON)\n",
     "    return at is not None and now - at <= HORIZON\n"),
    ("M6338", "a card without a time zone not said: never compared, never told why (VP1b)", PV,
     '    if at.tzinfo is None:                  # VP1b: never compared to an aware time, never guessed\n'
     '        return _said("no_tz")\n',
     ""),
    ("M6339", "a card without a time zone proposed: its zone guessed, taken for UTC (VP1b)", PV,
     '    if at.tzinfo is None:                  # VP1b: never compared to an aware time, never guessed\n'
     '        return _said("no_tz")\n',
     '    if at.tzinfo is None:\n'
     '        at = at.replace(tzinfo=timezone.utc)\n'),
    ("M6340", "the pass not held card by card: one card it cannot assess stops it (VP1b)", PV,
     "        try:\n"
     "            o = assess(c, cards, src)\n"
     "        except Exception as exc:          # the card skipped, the pass goes on (VP1b)\n",
     "        try:\n"
     "            o = assess(c, cards, src)\n"
     "        except ZeroDivisionError as exc:\n"),
    ("M6341", "a card the pass cannot assess said again at every pass (VP1b)", PV,
     "            if cid not in _SKIPPED:\n",
     "            if True:\n"),
    ("M6342", "a card of the wire without a time zone: which came first compared, the pass raises (VP1b)", PV,
     "    if any(t.tzinfo is None for t, _, _ in found):\n        return None, True\n",
     ""),
    ("M6343", "the error's own text said in the watch's channel, not its kind (VP1b)", PV,
     '                    say(f"card {cid[:8]} skipped by the proposed-verdict pass ({type(exc).__name__}): "\n',
     '                    say(f"card {cid[:8]} skipped by the proposed-verdict pass ({exc}): "\n'),
    ("M6344", "an empty suffix of the bot's signature: every message of the last 14 days edited at once (VP1b)",
     BOT,
     '    return f"{sig}|{state}" if state else sig\n',
     '    return f"{sig}|{state}"\n'),
    ("M6345", "after a confirmation, the VM's thread not archived — another path than a verdict's (VP1b)", BOT,
     "        # VP1b: the path of any verdict given — acknowledged, greyed, said, the thread archived.\n"
     "        await _judged(self, interaction,\n"
     "                      f\"{_VERDICT_WORDS.get(e['verdict'], discord_code(e['verdict']))} (proposé, confirmé) "
     "— jugé par **{who}**\")\n",
     "        esc_module.resolve(self.esc[\"id\"])\n"
     "        for item in self.view.children:\n"
     "            item.disabled = True\n"
     "        await interaction.response.edit_message(view=self.view)\n"
     "        await interaction.followup.send(\n"
     "            f\"{_VERDICT_WORDS.get(e['verdict'], discord_code(e['verdict']))} (proposé, confirmé) "
     "— jugé par **{who}**\")\n"),
    ("M6346", "a judged card archives its VM's thread though a card still waits in it (VP1b)", BOT,
     "    if not remaining and isinstance(interaction.channel, discord.Thread):\n"
     '        await interaction.channel.edit(archived=True, reason="All escalations handled")\n',
     "    if isinstance(interaction.channel, discord.Thread):\n"
     '        await interaction.channel.edit(archived=True, reason="All escalations handled")\n'),
]
TESTS = {
    "M6336": f"{_P}::test_confirmed_then_judged_by_hand_it_no_longer_says_proposed "
             f"{_B}::test_confirmed_then_judged_by_hand_the_bot_no_longer_says_proposed",
    "M6337": f"{_P}::test_a_card_without_a_time_zone_among_others_the_others_proposed",
    "M6338": f"{_P}::test_a_card_without_a_time_zone_among_others_the_others_proposed",
    "M6339": f"{_P}::test_a_card_without_a_time_zone_in_the_wire_which_came_first_is_never_guessed",
    "M6340": f"{_P}::test_a_card_the_pass_cannot_assess_is_skipped_said_once_the_others_proposed",
    "M6341": f"{_P}::test_a_card_the_pass_cannot_assess_is_skipped_said_once_the_others_proposed",
    "M6342": f"{_P}::test_a_card_without_a_time_zone_in_the_wire_which_came_first_is_never_guessed",
    "M6343": f"{_P}::test_a_card_the_pass_cannot_assess_is_skipped_said_once_the_others_proposed",
    "M6344": f"{_B}::test_an_empty_signature_suffix_edits_no_message_already_posted",
    "M6345": f"{_B}::test_after_a_confirmation_the_vms_thread_is_archived_as_after_a_verdict",
    "M6346": f"{_B}::test_a_confirmation_leaves_the_thread_open_while_a_card_still_waits_in_it",
}
