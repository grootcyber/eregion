"""SLF2 (#1010): Orodruin's writes in its exercise channel set aside from `data-exfiltration-blob` by its
identity, the channel's container and its account — never the address, nothing without the identity, said
—; a watch that restarts lets the record of the one before stand in, its identity only, at most as many
writes as the record holds in the window, an unreadable record standing in for nothing. One mutant per
property, M6927–M6941, measured by tests/unit/test_own_channel_slf2.py."""
OWN = "glorfindel/own_channel.py"
RULES = "glorfindel/detection_rules.py"
JS = "eregion_console/static/glorfindel.js"
_T = "tests/unit/test_own_channel_slf2.py"
_CONTAINER = ("    if str(entry.get(\"container\") or \"\") != exercise.container:\n        return None\n")
_WRITER = ("    if str(entry.get(\"writer\") or \"\").lower() != exercise.writer:\n        return None\n")
_MINE = "        mine = exercise is not None and bool(exercise.writer) and exercise.account == account\n"

MUTANTS = [
    ("M6927", "the exclusion by the address alone: every write of a row on the channel's account set aside, "
     "whoever wrote it, wherever (SLF2)", OWN,
     _CONTAINER + _WRITER,
     ""),
    ("M6928", "the container not checked: Orodruin's identity writing in another container set aside (SLF2)",
     OWN, _CONTAINER, ""),
    ("M6929", "the writer not checked: another identity writing in the exercise channel set aside (SLF2)",
     OWN, _WRITER, ""),
    ("M6930", "set aside without a configuration: no identity matches a write without one, a key or a SAS "
     "(SLF2)", OWN,
     _MINE,
     "        mine = exercise is not None and exercise.account == account\n"),
    ("M6931", "the configuration missing no longer said in the rule's status (SLF2)", RULES,
     "                    **({\"config\": exercise_config} if exercise_config else {}),\n",
     ""),
    ("M6932", "the account lost: a container of that name on another account set aside (SLF2)", OWN,
     _MINE,
     "        mine = exercise is not None and bool(exercise.writer)\n"),
    ("M6933", "the record taken for « all known »: every write of its identity set aside at restart, past the "
     "number it holds (SLF2)", OWN,
     "        return Channel(account, container, previous.writer, budget=n) if n > 0 else Channel(account, container, \"\")\n",
     "        return Channel(account, container, previous.writer, budget=None) if n > 0 else Channel(account, container, \"\")\n"),
    ("M6934", "a record past its bound read whole, as if readable (SLF2)", OWN,
     "            data = f.read(STATE_MAX + 1)\n        if len(data) > STATE_MAX:\n            return None\n",
     "            data = f.read()\n"),
    ("M6935", "the record of another channel taken for this one's (SLF2)", OWN,
     "    if not isinstance(raw, dict) or raw.get(\"account\") != account or raw.get(\"container\") != container:\n",
     "    if not isinstance(raw, dict):\n"),
    ("M6936", "the record's writes past the rule's window still vouched for (SLF2)", OWN,
     "        return sum(1 for w in self.writes if now - timedelta(seconds=LOOKBACK_S) <= w <= now)\n",
     "        return sum(1 for w in self.writes if w <= now)\n"),
    ("M6937", "another identity accepted at restart: the record stands in once the watch's own identity is "
     "read, and it is another (SLF2)", OWN,
     "        if oid or previous is None:\n            return Channel(account, container, oid)\n",
     "        if previous is None:\n            return Channel(account, container, oid)\n"),
    ("M6938", "the record carried over to another identity: the writes of the one before counted under the "
     "new one (SLF2)", OWN,
     "            if oid != self._oid:\n                self._oid, self._writes = oid, []\n",
     "            self._oid = oid\n"),
    ("M6939", "Orodruin's writes set aside no longer counted in the rule's status (SLF2)", RULES,
     "                    \"writes\": was[\"exercise_channel_count\"] + own.get(\"exercise_writes\", 0),\n",
     "                    \"writes\": was[\"exercise_channel_count\"],\n"),
    ("M6940", "Orodruin's writes set aside no longer said in the watch's log (SLF2)", RULES,
     "        if own.get(\"exercise_writes\"):\n            logger.info(",
     "        if False:\n            logger.info("),
    ("M6941", "Orodruin's writes set aside no longer shown on the rule's line in the console (SLF2)", JS,
     "      ${oro}\n      ${mt}\n",
     "      ${mt}\n"),
]
TESTS = {
    "M6927": f"{_T}::test_another_writer_container_or_account_stays_a_card",
    "M6928": f"{_T}::test_another_writer_container_or_account_stays_a_card",
    "M6929": f"{_T}::test_another_writer_container_or_account_stays_a_card",
    "M6930": f"{_T}::test_settle_without_an_identity_sets_nothing_aside",
    "M6931": f"{_T}::test_without_orodruin_s_identity_nothing_is_set_aside_and_the_status_says_it",
    "M6932": f"{_T}::test_another_writer_container_or_account_stays_a_card",
    "M6933": f"{_T}::test_more_writes_than_the_record_holds_stay_a_card",
    "M6934": f"{_T}::test_an_unreadable_record_never_stands_in",
    "M6935": f"{_T}::test_an_unreadable_record_never_stands_in",
    "M6936": f"{_T}::test_an_unreadable_record_never_stands_in",
    "M6937": f"{_T}::test_once_its_identity_is_read_the_record_stands_in_for_nothing",
    "M6938": f"{_T}::test_the_publisher_keeps_the_record_for_the_next_watch",
    "M6939": f"{_T}::test_the_line_of_orodruin_of_the_21_11_through_the_sdk_is_set_aside_and_said",
    "M6940": f"{_T}::test_the_line_of_orodruin_of_the_21_11_through_the_sdk_is_set_aside_and_said",
    "M6941": f"{_T}::test_the_console_says_orodruin_s_writes_and_the_restart_on_the_rule",
}
