"""SLF1 (#929): the watch's own return channel set aside from `data-exfiltration-blob` — its
identity, the container of its configured channel, the objects it writes there, and nothing else —,
said; a card on a detection attributed to no VM says so, never one VM as its resource. One mutant per
property, M6391–M6405, measured by tests/unit/test_own_channel.py (and, for the attribution guard,
tests/unit/test_agent_nodes.py)."""
OWN = "glorfindel/own_channel.py"
RULES = "glorfindel/detection_rules.py"
AGENT = "glorfindel/agent.py"
_T = "tests/unit/test_own_channel.py"

MUTANTS = [
    ("M6391", "the exclusion widened to the address: a row that holds the watch's own writes is left out "
     "whole, another write from that address with it (SLF1)", OWN,
     "        if total - writes <= 0:\n",
     "        if writes > 0:\n"),
    ("M6392", "the exclusion widened to the account: the watch's writes in any container of the channel's "
     "account set aside (SLF1)", OWN,
     "    if str(entry.get(\"container\") or \"\") != channel.container:\n        return None\n",
     ""),
    ("M6393", "the exclusion widened to every identity: another identity's writes in the channel's container "
     "set aside (SLF1)", OWN,
     "    if str(entry.get(\"writer\") or \"\").lower() != channel.writer:\n        return None\n",
     ""),
    ("M6394", "the exclusion read on any account: a container of that name on another account set aside "
     "(SLF1)", OWN,
     "        if (total is None or not isinstance(writers, list)\n"
     "                or str(row.get(\"AccountName\") or \"\").lower() != channel.account):\n",
     "        if (total is None or not isinstance(writers, list)):\n"),
    ("M6395", "the exclusion read on any object: the watch's identity writing anything in its container set "
     "aside (SLF1)", OWN,
     "    if writes is None or writes <= 0 or known != writes:\n",
     "    if writes is None or writes <= 0:\n"),
    ("M6396", "the exclusion no longer said in the rule's status (SLF1)", RULES,
     "            if own[\"writes\"] or own[\"unread\"]:\n",
     "            if own[\"unread\"]:\n"),
    ("M6397", "the exclusion no longer said in the watch's log (SLF1)", RULES,
     "        if own[\"writes\"]:\n            logger.info(",
     "        if False:\n            logger.info("),
    ("M6398", "the exclusion applied without a channel configured: every write of a channel's shape set "
     "aside (SLF1)", OWN,
     "        if channel is None:\n            out.append(row)\n            continue\n",
     "        if channel is None:\n"
     "            if all(isinstance(e, dict) and e.get(\"known\") == e.get(\"writes\") for e in writers or [{}]):\n"
     "                said[\"rows\"] += 1\n                continue\n"
     "            out.append(row)\n            continue\n"),
    ("M6399", "the watch's identity not read taken for any writer: the writes without an identity set aside, "
     "unsaid (SLF1)", OWN,
     "        if not channel.writer:\n            said[\"unread\"] = True\n            out.append(row)\n"
     "            continue\n",
     ""),
    ("M6400", "the column of the writers left in the row: what the model reads changes (SLF1)", OWN,
     "        writers = row.pop(WRITERS)\n",
     "        writers = row.get(WRITERS)\n"),
    ("M6401", "the Discord card of an unattributed detection names the VM it is filed on (SLF1)",
     "glorfindel/bot.py",
     "        loose = esc_module.unattributed(esc)\n        if loose is not None:\n",
     "        loose = None\n        if loose is not None:\n"),
    ("M6402", "the CLI's card of an unattributed detection names the VM it is filed on (SLF1)",
     "glorfindel/cli.py",
     "    loose = _esc.unattributed(e)\n    if loose is not None:\n",
     "    loose = _esc.unattributed(e)\n    if False:\n"),
    ("M6403", "the card of an unattributed detection no longer says so: its attribution not recorded (SLF1)",
     AGENT,
     "    if ctx.get(\"attribution\") != \"unattributed\" or _card_target(signal) is not None:\n        return None\n"
     "    cands = ctx.get(\"candidates\")\n",
     "    return None\n    cands = ctx.get(\"candidates\")\n"),
    ("M6404", "an unattributed detection folded into its anchor VM's card, counted as that VM's (SLF1)",
     "glorfindel/escalations.py",
     "                and _attribution_of(e) == _attribution_of({\"attribution\": None if target else attribution})\n",
     ""),
    ("M6405", "the attribution guard bypassed: an isolation of the VM an unattributed detection is anchored "
     "on runs (SLF1)", AGENT,
     "    if ctx.get(\"attribution\") != \"unattributed\":\n        return\n    candidates = ",
     "    if True:\n        return\n    candidates = "),
]
TESTS = {
    "M6391": f"{_T}::test_another_write_from_the_watch_s_address_stays_a_card",
    "M6392": f"{_T}::test_another_write_from_the_watch_s_address_stays_a_card",
    "M6393": f"{_T}::test_a_write_in_the_channel_by_another_identity_stays_a_card",
    "M6394": f"{_T}::test_another_account_with_a_container_of_that_name_stays_a_card",
    "M6395": f"{_T}::test_an_object_the_channel_does_not_hold_stays_a_card",
    "M6396": f"{_T}::test_the_watch_s_own_writes_make_no_card_and_are_said",
    "M6397": f"{_T}::test_the_watch_s_own_writes_make_no_card_and_are_said",
    "M6398": f"{_T}::test_without_a_channel_configured_nothing_is_set_aside",
    "M6399": f"{_T}::test_the_watch_s_identity_not_read_sets_nothing_aside_and_says_so",
    "M6400": f"{_T}::test_the_message_to_the_model_is_the_one_of_before_to_the_byte",
    "M6401": f"{_T}::test_the_discord_card_says_not_attributed_never_its_anchor",
    "M6402": f"{_T}::test_an_unattributed_card_says_so_and_names_its_candidates",
    "M6403": f"{_T}::test_an_unattributed_card_says_so_and_names_its_candidates",
    "M6404": f"{_T}::test_an_unattributed_detection_never_folds_into_its_anchor_s_card",
    "M6405": (f"{_T}::test_an_unattributed_card_says_so_and_names_its_candidates "
              "tests/unit/test_agent_nodes.py::test_unattributed_detection_holds_isolation_and_ip_block"),
}
