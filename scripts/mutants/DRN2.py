"""DRN2 (#754): the session cut announced pending gets one closure — its outcome, when it was read so
— in the VM's Discord thread when the bot is configured, else by the webhook, and the console's
card says it. Once per cut, by its nonce, after a restart of the watch or of the bot too; its card,
then the state (the outcome read on Azure, its closure due), then the closure (L1A). M4890–M4899;
the review (round 1: a notice decides nothing, a store unreadable never stops the follow, a cut
asked again before its end): M4905–M4909. Measured by tests/unit/test_drain_closure.py and
tests/unit/test_drain_console.py."""
WATCH = "glorfindel/drain_watch.py"
NOTICES = "glorfindel/vm_notices.py"
BOT = "glorfindel/bot.py"
API = "eregion_console/api.py"
RUN = "glorfindel/providers/azure/run_command.py"
_T = "tests/unit/test_drain_closure.py"
_C = "tests/unit/test_drain_console.py"

MUTANTS = [
    ("M4890", "a cut read drained at the next pass closed in silence: the bench of 12/11 back, the card "
     "and Discord left on « coupure en attente » (DRN2)", WATCH,
     '    via = vm_notices.say(rid, closure_key(rid, ended.get("asked_at")), "drain_closed", title, text,\n'
     '                         level=level, detail={"outcome": case or "drained", "after_s": after})\n',
     '    via = "none"\n'),
    ("M4891", "a closure said again for the same cut: every pass that reads it posts a new message (DRN2)",
     NOTICES,
     '        if any(n["key"] == notice["key"] for n in notices):\n',
     "        if False:\n"),
    ("M4892", "the closure's mark taken off before it is said: a store full, or the watch stopped, and the "
     "cut is never closed (L1A, DRN2 review)", WATCH,
     "        _say_closed(vm, rid, drain, after, report, read=due.get(\"read\") is True)\n"
     "    _save_isolation_state(rid, {k: v for k, v in state.items() if k != \"drain_closure_due\"})\n",
     "        _save_isolation_state(rid, {k: v for k, v in state.items() if k != \"drain_closure_due\"})\n"
     "        _say_closed(vm, rid, drain, after, report, read=due.get(\"read\") is True)\n"),
    ("M4893", "« relue » said of a cut nothing read: the watch restarted, its poller lost (DRN2 review)",
     WATCH,
     '    word = "relue " if read else ""\n',
     '    word = "relue "\n'),
    ("M4894", "the webhook speaks too while the bot is configured: the closure posted twice, in the channel "
     "and in the VM's thread (DRN2)", NOTICES,
     '    if notice["via"] == "webhook":\n',
     '    if notice["via"] in ("webhook", "bot"):\n'),
    ("M4895", "a restarted bot forgets what it posted: every closure posted again in its thread (DRN2)", BOT,
     "        return {str(k) for k in json.loads(_NOTICES_POSTED_STORE.read_text())}\n",
     "        return set()\n"),
    ("M4896", "a VM released before the end of its cut: what was announced pending never closed (DRN2)",
     WATCH,
     "    if vm_notices.said(key) is not None:\n        return\n",
     "    return\n"),
    ("M4897", "a closure pings the role: « Incident opened » for a cut that succeeded (DRN2)", BOT,
     "                thread = await self._get_or_create_thread(channel, key, ping=False)\n",
     "                thread = await self._get_or_create_thread(channel, key)\n"),
    ("M4898", "the console's card says nothing of a cut that failed: only « sessions cut » is shown (DRN2)",
     API,
     '    case = drain_case(drain) or ("drained" if drain.get("status") == "drained" else "")\n',
     '    case = "drained" if drain.get("status") == "drained" else ""\n'),
    ("M4899", "the closure's text posted raw in the VM's thread: a masked link or @everyone from outside "
     "reaches Discord (SEC6, DRN2)", NOTICES,
     "            f\"> {discord_text(' '.join(str(notice.get('text', '')).split())[:1500])}\")\n",
     "            f\"> {' '.join(str(notice.get('text', '')).split())[:1500]}\")\n"),
    ("M4905", "an outcome written with its closure due, never said after a restart: the mark read by no "
     "pass (DRN2 review)", WATCH,
     '            if snap.get("drain_closure_due"):     # an outcome written, its closure not said yet\n',
     "            if False:\n"),
    ("M4906", "the console takes a notice's words for the card whatever the outcome: a forged « aboutie » "
     "on a cut that never ended (DRN2 review)", API,
     '    if (notice.get("detail") or {}).get("outcome") != case:\n        notice = {}\n',
     ""),
    ("M4907", "bytes that are not UTF-8 in the notices' store stop the follow of every cut (DRN2 review)",
     NOTICES,
     '    for line in _STORE.read_bytes().decode("utf-8", errors="replace").splitlines():\n',
     '    for line in _STORE.read_bytes().decode("utf-8").splitlines():\n'),
    ("M4908", "a notices' store that cannot be read stops the bot's turn: its cards, its week, its sync "
     "frozen (DRN2 review)", BOT,
     "        try:\n            notices = vm_notices.for_bot()\n"
     "        except (OSError, ValueError) as e:   # the store unreadable: said, read again next turn\n",
     "        try:\n            notices = vm_notices.for_bot()\n"
     "        except ValueError as e:   # the store unreadable: said, read again next turn\n"),
    ("M4909", "a cut asked again before its end: the first one's poller replaced, never closed (DRN2 "
     "review)", RUN,
     '            _SUPERSEDED.setdefault(key, []).append(before["asked_at"])\n',
     "            pass\n"),
]
TESTS = {**{mid: _T for mid in ("M4890", "M4891", "M4892", "M4893", "M4894", "M4895", "M4896", "M4897",
                                 "M4899", "M4905", "M4907", "M4908", "M4909")},
         "M4898": _C, "M4906": _C}
