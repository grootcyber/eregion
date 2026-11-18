"""DRL1b (#613): the drill of the week on Imladris's side — each occurrence's verdict, the absence
alarm, the bot's thread (docs/design/drill-banc.md §4.2, §9). glorfindel/drill_watch.py, the pull of
eregion_core/exercise_channel.py (``pull_drill``), glorfindel/bot.py (``_post_drill``). M5861–M5880,
measured by tests/unit/test_drill_watch.py. M5861–M5863 are the one §9 gives DRL1b: the absence alarm
armed on a drill disarmed, or killed, or on a fingerprint Imladris does not have.
"""
DW = "glorfindel/drill_watch.py"
XC = "eregion_core/exercise_channel.py"
BOT = "glorfindel/bot.py"
T = "tests/unit/test_drill_watch.py::"

MUTANTS = [
    ("M5861", "the absence alarm armed on a drill.json that says disarmed (drill_changed, the permit still "
     "there): not_run at an hour the Orodruin of before does not know (DRL1b, §9)", DW,
     '    if pulse["state"] != "armed":   # disarmed by drill_changed, the permit still there\n',
     "    if False:\n"),
    ("M5862", "the absence alarm armed on a fingerprint Imladris does not have: the permit's and the pulse's "
     "never compared with this host's copy (DRL1b, §9)", DW,
     '    if copy is None or permit["sha256"] != sha or pulse["sha256"] != sha \\\n'
     '            or permit["drill"] != name or pulse["drill"] != name:\n',
     "    if copy is None:\n"),
    ("M5863", "a drill killed not taken for disarmed: only the operator's disarming says nothing (DRL1b, §9)",
     DW,
     '        if pulse is None or (pulse["state"] == "disarmed" and pulse["reason"] != "drill_changed"):\n',
     '        if pulse is None or pulse["reason"] == "operator":\n'),
    ("M5864", "the permit judged by drill.json instead of the channel's listing (DRL1b)", DW,
     '    listed = permit_seen.get("listed") is True\n',
     '    listed = pulse is not None and pulse["state"] == "armed"\n'),
    ("M5865", "the drill read as drill.find does: a drill of the instance named as the shipped one gives "
     "the hour and the fingerprint (DRL1b)", DW,
     '            d, sha = dr.loaded(Path(self.drills_dir or dr.shipped_dir()) / f"{name}.yaml", dr.SHIPPED)\n',
     '            own = dr.instance_dir() / f"{name}.yaml"\n'
     '            d, sha = dr.loaded(own if own.exists() else Path(self.drills_dir or dr.shipped_dir()) / '
     'f"{name}.yaml", dr.SHIPPED)\n'),
    ("M5866", "the channel unread judged as listed: channel_unread arms not_run (DRL1b)", DW,
     '    if not seen["listed"]:\n',
     '    if not seen["listed"] and False:\n'),
    ("M5867", "unknown with a mention the first time (§4.2: only two in a row) (DRL1b)", DW,
     '        return previous == "unknown"\n',
     "        return True\n"),
    ("M5868", "every refusal with a mention: drill_changed and no_permit too, expected after a release, a "
     "kill, a permit expired (DRL1b)", DW,
     "        return code not in REFUSED_QUIET\n",
     "        return True\n"),
    ("M5869", "no refusal with a mention: passive, not_placed, not_bench, off_schedule, too_soon, "
     "permit_mismatch said quietly (DRL1b)", DW,
     "        return code not in REFUSED_QUIET\n",
     "        return False\n"),
    ("M5870", "the channel unread eight days in a row, still without a mention: it hides « Orodruin silent » "
     "(DRL1b)", DW,
     "        return unread_s >= UNREAD_MENTION_S\n",
     "        return False\n"),
    ("M5871", "the channel unread with a mention from its first pull (DRL1b)", DW,
     "        return unread_s >= UNREAD_MENTION_S\n",
     "        return True\n"),
    ("M5872", "missed without a mention: a regression said quietly (DRL1b)", DW,
     '    if state in ("missed", "not_run", "self_disarmed"):\n',
     '    if state in ("not_run", "self_disarmed"):\n'),
    ("M5873", "the bot's text outside glorfindel/chat_text.py: a said written raw (DRL1b)", DW,
     '    said = discord_text(" ".join(str(v.get("said") or "").split())[:900])\n',
     '    said = " ".join(str(v.get("said") or "").split())[:900]\n'),
    ("M5874", "the bot mentions the role where §4.2 puts no mention (DRL1b)", BOT,
     '        if v.get("mention") and self.ping_role:\n',
     "        if self.ping_role:\n"),
    ("M5875", "the bot posts a quiet verdict (disarmed, waiting) (DRL1b)", BOT,
     '        if not isinstance(v, dict) or not drill_watch.alerts(v) or not v.get("drill"):\n',
     '        if not isinstance(v, dict) or not v.get("drill"):\n'),
    ("M5876", "the bot posts a verdict again after its restart (DRL1b)", BOT,
     "        if k in self._drill_posted:\n            return False\n",
     ""),
    ("M5877", "the permit kept from an earlier pull: a permit removed from the channel still seen (DRL1b)", XC,
     '    permit = {"listed": False, "doc": None, "why": ""}\n',
     '    permit = before.get("permit") or {"listed": False, "doc": None, "why": ""}\n'),
    ("M5878", "a listing that fails taken for one that went through: the permit « absent », never « unread » "
     "(DRL1b)", XC,
     '        seen = {"at": at, "listed": False, "why": f"{type(e).__name__}: {e}"[:300],\n',
     '        seen = {"at": at, "listed": True, "why": f"{type(e).__name__}: {e}"[:300],\n'),
    ("M5879", "the first moment of an unread channel forgotten at each pull: eight days in a row never "
     "reached (DRL1b)", XC,
     '                "unread_since": (str(before.get("unread_since") or at) if before.get("listed") is False else at),\n',
     '                "unread_since": at,\n'),
    ("M5880", "not_run before two hours after the occurrence's hour (DRL1b)", DW,
     "    if (now - o).total_seconds() < NOT_RUN_AFTER_S:\n",
     "    if False:\n"),
]
TESTS = {
    "M5861": T + "test_drill_changed_on_orodruin_the_occurrence_refused_without_mention_then_rearm",
    "M5862": T + "test_a_fingerprint_imladris_does_not_have_rearm_expected",
    "M5863": T + "test_drill_json_disarmed_by_the_operator_or_the_kill_says_nothing",
    "M5864": T + "test_no_permit_listed_and_drill_json_armed_rearm_expected_never_not_run",
    "M5865": T + "test_the_hour_and_the_fingerprint_are_this_hosts_copy_never_the_instances",
    "M5866": T + "test_the_channel_unread_arms_neither_not_run_nor_rearm_expected",
    "M5867": T + "test_unknown_without_mention_the_first_time_with_one_two_in_a_row",
    "M5868": T + "test_refused_its_mention_by_its_code_as_the_table",
    "M5869": T + "test_refused_its_mention_by_its_code_as_the_table",
    "M5870": T + "test_the_channel_unread_eight_days_in_a_row_mentions",
    "M5871": T + "test_the_channel_unread_arms_neither_not_run_nor_rearm_expected",
    "M5872": T + "test_missed_a_regression_with_a_mention",
    "M5873": T + "test_the_bots_text_passes_by_chat_text",
    "M5874": T + "test_the_bot_mentions_no_one_where_the_table_does_not",
    "M5875": T + "test_a_quiet_verdict_is_never_posted",
    "M5876": T + "test_the_bot_posts_in_the_drills_own_thread_once_mentioning_the_role",
    "M5877": T + "test_the_permit_absent_from_the_listing_is_absent_whatever_was_seen_before",
    "M5878": T + "test_a_listing_that_fails_is_unread_never_absent_and_its_first_moment_kept",
    "M5879": T + "test_a_listing_that_fails_is_unread_never_absent_and_its_first_moment_kept",
    "M5880": T + "test_not_run_when_everything_agrees_and_no_status_two_hours_after",
}
