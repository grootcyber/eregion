"""JUG2b (#768): the webhook fallback of JUG2 never holds the watch's loop — its pass in a thread of its
own, one at a time, stopped at a webhook unreachable or its budget spent, each POST bounded —; the
tries of a notice capped; the bot's SIGTERM handler put back; and a cut's closure falls back too,
never pinging (Jonathan, 12/11). M5005–M5014. The review (round 1) took three of them back for its
findings — M5006 (was: two passes at once), M5009 (was: no budget), M5011 (was: a try never counted):
their tests stay (test_one_relay_pass_at_a_time, test_a_pass_starts_no_post_once_its_budget_spent,
the cap's tests), the range held. Measured by tests/unit/test_bot_fallback.py."""
NOTICES = "glorfindel/vm_notices.py"
BOT = "glorfindel/bot.py"
CLI = "glorfindel/cli.py"
_T = "tests/unit/test_bot_fallback.py"

MUTANTS = [
    ("M5005", "the relay pass back in the watch's loop: a webhook that does not answer holds its heartbeat, "
     "its reassertion, runs/ and « Verify » (JUG2b)", CLI,
     '        _relay_thread[0] = _thr.Thread(target=_run, daemon=True, name="relay-notices")\n'
     "        _relay_thread[0].start()\n",
     "        _run()\n"),
    ("M5006", "a pass goes on past a webhook that refuses (a 404, deleted): a post per notice due at "
     "every pass, all refused (JUG2b review)", NOTICES,
     '                  "unreachable",\n                  "refused")',
     '                  "unreachable")'),
    ("M5007", "a pass goes on past a webhook unreachable: up to a deadline per announcement, every pass "
     "(JUG2b)", NOTICES,
     '                  "unreachable",\n',
     ""),
    ("M5008", "a POST without a deadline: a name that does not resolve, a webhook that never answers, "
     "hold the caller as long as they will (JUG2b)", NOTICES,
     "    if not _wait(done, POST_DEADLINE_S):\n",
     "    if not _wait(done, None):\n"),
    ("M5009", "a cut's closure posted by `say`, from the reassertion under its VM's lock: a webhook that "
     "does not answer holds an isolation of the same VM up to 25 s (JUG2b review)", NOTICES,
     '    why = relay_reason() if notice["via"] == "bot" and kind == ACTION_KIND else ""\n',
     '    why = relay_reason() if notice["via"] == "bot" and kind in RELAY_KINDS else ""\n'),
    ("M5010", "no cap on the tries: a webhook that delivers but whose answer is lost pings at every pass "
     "for 24 h (JUG2b)", NOTICES,
     "            if _tries(n) >= RELAY_MAX_TRIES:\n                continue",
     "            if False:\n                continue"),
    ("M5011", "a post that left nothing (a name not resolved, a connection refused or not made in time) "
     "counts a try: three minutes of network cut silence the fallback (JUG2b review)", NOTICES,
     '            if _nothing_sent(exc):\n                return "unsent"\n',
     ""),
    ("M5012", "the bot's SIGTERM handler left installed after `run()`: a caller that goes on reads "
     "SIGTERM as a Ctrl-C (JUG2b)", BOT,
     "        _restore_sigterm(previous)\n",
     ""),
    ("M5013", "the bot mute, a cut's closure waits for it: a drained or a failed cut said nowhere, and "
     "lost after 24 h (JUG2b)", NOTICES,
     "RELAY_KINDS = (ACTION_KIND, CLOSURE_KIND)\n",
     "RELAY_KINDS = (ACTION_KIND,)\n"),
    ("M5014", "a cut's closure relayed pings the role: a ping for what is no action taken alone (JUG1, "
     "JUG2b)", NOTICES,
     '    ping = bool(notice.get("kind") == ACTION_KIND\n                and _ping_role()',
     "    ping = bool(True\n                and _ping_role()"),
]
TESTS = {mid: _T for mid, *_ in MUTANTS}
