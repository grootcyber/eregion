"""JUG2 (#765): the Discord bot mute (its heartbeat absent, stale, or dated in the future), the webhook
says an action Glorfindel took alone — once, the role pinged, no other mention allowed; the bot alive,
nothing changes from JUG1; the bot back, nothing twice; a beat forged fresh only delays. M4970–M4979;
the review (a webhook that fails, `docker stop`, a burst): M4995–M4999. Measured by
tests/unit/test_bot_fallback.py."""
NOTICES = "glorfindel/vm_notices.py"
BEAT = "glorfindel/bot_beat.py"
BOT = "glorfindel/bot.py"
_T = "tests/unit/test_bot_fallback.py"

MUTANTS = [
    ("M4970", "the bot stopped, the action still left to it: announced nowhere until it comes back, and "
     "lost after 24 h (JUG2)", NOTICES,
     '    why = relay_reason() if notice["via"] == "bot" and kind == ACTION_KIND else ""\n',
     '    why = ""\n'),
    ("M4971", "a heartbeat hours old reads alive: a bot stopped long ago still takes the announcements "
     "(JUG2)", BEAT,
     '    return "stale" if age > MUTE_AFTER_S else ""\n',
     '    return ""\n'),
    ("M4972", "a heartbeat dated a year ahead reads alive: written once, it holds the fallback forever "
     "(JUG2)", BEAT,
     '    if age < -FUTURE_SLACK_S:\n        return "future"\n',
     ""),
    ("M4973", "a heartbeat kept fresh by another writer holds an announcement the bot never posts: it "
     "silences, not only delays (JUG2)", NOTICES,
     '            why = mute or ("unconfirmed" if (now - at).total_seconds() >= CONFIRM_S else "")\n',
     "            why = mute\n"),
    ("M4974", "the webhook pinged for the action, then the bot back pings again with its card: two pings "
     "for one action (JUG2)", BOT,
     '                    if self.ping_role and not vm_notices.relayed_ping(esc.get("action_keys")) else {})\n',
     "                    if self.ping_role else {})\n"),
    ("M4975", "the bot posts an announcement the webhook said since it read its notices: said twice "
     "(JUG2)", BOT,
     '            if current is not None and current.get("via") != "bot":\n',
     "            if False:\n"),
    ("M4976", "the bot never writes its heartbeat: alive, it reads mute, and every action goes by the "
     "webhook into the channel (JUG2)", BOT,
     "                    bot_beat.write()\n",
     "                    pass\n"),
    ("M4977", "the fallback's message allows every mention: a name from outside could ping @everyone or "
     "a user (SEC6, JUG2)", NOTICES,
     '             "allowed_mentions": {"parse": [], "roles": [role] if role else []}}, notice["key"], native)\n',
     '             "allowed_mentions": {"parse": ["everyone", "roles", "users"]}}, notice["key"], native)\n'),
    ("M4978", "an announcement the bot posted is said again by the webhook once the bot falls silent "
     "(JUG2)", NOTICES,
     # The review: its anchor follows relay_pass (a mark never noted sent taken back first).
     '            if n.get("via") != "bot" or n["key"] in posted:\n',
     '            if n.get("via") != "bot":\n'),
    ("M4979", "the bot posted the card and its ping, then fell silent: the webhook pings again for the "
     "same action (JUG2)", NOTICES,
     '                and not _card_posted(str((notice.get("detail") or {}).get("card") or "")))\n',
     "                )\n"),
]
# The review (round 1): a webhook that fails, `docker stop`, a burst — M4995–M4999.
MUTANTS += [
    ("M4995", "a webhook that answers 429, 404 or 500 counts as said: the announcement lost, and the card "
     "at the bot's return without its ping (JUG2 review)", NOTICES,
     '        if isinstance(status, int) and 200 <= status < 300:\n            return "sent"\n',
     '        if True:\n            return "sent"\n'),
    ("M4996", "a relay that failed stays marked said: neither the next pass nor the bot says it again "
     "(JUG2 review)", NOTICES,
     '                    n["via"] = "bot"\n                    n.pop("relayed")\n',
     "                    pass\n"),
    ("M4997", "a relay marked but never noted sent silences the card's ping: the role pinged by no one "
     "(JUG2 review)", NOTICES,
     '                                and (n.get("relayed") or {}).get("sent") is True\n',
     ""),
    ("M4998", "`docker stop` leaves the bot's beat: SIGTERM ignored by PID 1, the fallback waits 3 min and "
     "a pass (JUG2 review)", BOT,
     "    _stop_on_sigterm()\n",
     ""),
    ("M4999", "a pass posts its relayed announcements back to back: Discord's 429 loses part of a burst "
     "(JUG2 review)", NOTICES,
     "        if i:\n            _sleep(RELAY_SPACING_S)\n",
     ""),
]
TESTS = {mid: _T for mid, *_ in MUTANTS}
