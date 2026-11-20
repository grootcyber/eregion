"""VP1c (#920): TO JUDGE and the observation report hold before a card whose time carries no time
zone — never compared to an aware time, never taken for UTC, the card kept in TO JUDGE and flagged
(glorfindel/escalations.py); the bot keeps it in line, judged, never acted on (glorfindel/bot.py).
M6366–M6375, measured by tests/unit/test_observation.py and tests/unit/test_bot.py."""
ESC = "glorfindel/escalations.py"
BOT = "glorfindel/bot.py"
_O = "tests/unit/test_observation.py"
_B = "tests/unit/test_bot.py"

MUTANTS = [
    ("M6366", "TO JUDGE compares a card's time without a zone to an aware since: the whole list falls (VP1c)", ESC,
     "        at = _zoned(e)\n"
     "        if since is not None and at is not None and at < since:\n",
     "        at = _when(e)\n"
     "        if since is not None and at is not None and at < since:\n"),
    ("M6367", "the observation report compares a card's time without a zone to an aware since: it falls (VP1c)",
     ESC,
     "            at = _zoned(e)\n"
     "            if at is None:                  # VP1c: in the window or not, unknown — said, never guessed\n",
     "            at = _when(e)\n"
     "            if at is None:                  # VP1c: in the window or not, unknown — said, never guessed\n"),
    ("M6368", "the recurrence compares a time without a zone to one with a zone: TO JUDGE falls, since or not (VP1c)",
     ESC,
     "    ip, me = _ip_of(e), _zoned(e)          # VP1c: only times with a zone are ever compared\n",
     "    ip, me = _ip_of(e), _when(e)\n"),
    ("M6369", "a card's time without a zone taken for UTC: dated by a guess, left out of TO JUDGE's week (VP1c)",
     ESC,
     "    return at if at is not None and at.tzinfo is not None else None\n",
     "    return at.replace(tzinfo=timezone.utc) if at is not None and at.tzinfo is None else at\n"),
    ("M6370", "a card whose time cannot be placed disappears from TO JUDGE as soon as there is a since (VP1c)", ESC,
     "        if since is not None and at is not None and at < since:\n",
     "        if since is not None and (at is None or at < since):\n"),
    ("M6371", "a card whose time cannot be placed stays in TO JUDGE unflagged: dated as any other (VP1c)", ESC,
     '        card["time_unreadable"] = at is None\n',
     '        card["time_unreadable"] = False\n'),
    ("M6372", "a card whose time cannot be placed sorted last: a limit cuts it out of TO JUDGE (VP1c)", ESC,
     "    out.sort(key=lambda p: (p[0] is None, p[0].timestamp() if p[0] is not None else 0.0), reverse=True)\n",
     "    out.sort(key=lambda p: (False, p[0].timestamp() if p[0] is not None else 0.0), reverse=True)\n"),
    ("M6373", "the observation report leaves a card out of its window without saying it (VP1c)", ESC,
     "                undated += 1\n",
     ""),
    ("M6374", "the bot's sync compares a card's time without a zone to an aware now: the sync falls (VP1c)", BOT,
     "        if when is not None and (when.tzinfo is None or now - when <= timedelta(days=_RESTORE_DAYS)):\n",
     "        if when is not None and now - when <= timedelta(days=_RESTORE_DAYS):\n"),
    ("M6375", "a card of unknown age acted on from the bot, as one of known age (VP1c)", BOT,
     '        if kind != "judge":\n'
     '            return "heure illisible (sans fuseau)"\n',
     "        pass\n"),
]
TESTS = {
    "M6366": f"{_O}::test_to_judge_keeps_a_card_without_a_time_zone_flagged_whatever_since",
    "M6367": f"{_O}::test_the_report_leaves_out_a_card_without_a_time_zone_and_says_it",
    "M6368": f"{_O}::test_to_judge_holds_cards_with_and_without_a_zone_on_one_ip_without_since "
             f"{_O}::test_recurrence_compares_only_times_with_a_zone",
    "M6369": f"{_O}::test_to_judge_keeps_a_card_without_a_time_zone_flagged_whatever_since",
    "M6370": f"{_O}::test_to_judge_keeps_a_card_without_a_time_zone_flagged_whatever_since",
    "M6371": f"{_O}::test_to_judge_keeps_a_card_without_a_time_zone_flagged_whatever_since",
    "M6372": f"{_O}::test_to_judge_holds_cards_with_and_without_a_zone_on_one_ip_without_since",
    "M6373": f"{_O}::test_the_report_leaves_out_a_card_without_a_time_zone_and_says_it",
    "M6374": f"{_B}::test_a_card_without_a_time_zone_stays_in_line_judged_never_acted_on",
    "M6375": f"{_B}::test_a_card_without_a_time_zone_stays_in_line_judged_never_acted_on",
}
