"""DRN2 (#754): the session cut announced pending gets one closure — its outcome, when it was read so
— in the VM's Discord thread when the bot is configured, else by the webhook, and the console's
card says it. Once per cut, by its nonce, after a restart of the watch or of the bot too; its card,
then its closure, then the state (L1A). M4890–M4899, measured by tests/unit/test_drain_closure.py
and tests/unit/test_drain_console.py."""
WATCH = "glorfindel/drain_watch.py"
NOTICES = "glorfindel/vm_notices.py"
BOT = "glorfindel/bot.py"
API = "eregion_console/api.py"
_T = "tests/unit/test_drain_closure.py"
_C = "tests/unit/test_drain_console.py"

MUTANTS = [
    ("M4890", "a cut read drained at the next pass closed in silence: the bench of 12/11 back, the card "
     "and Discord left on « coupure en attente » (DRN2)", WATCH,
     '    via = vm_notices.say(rid, closure_key(rid, ended.get("asked_at")), "drain_closed", title, text,\n'
     '                         level=level, detail={"outcome": case or "drained", "after_s": after, "drain": ended})\n',
     '    via = "none"\n'),
    ("M4891", "a closure said again for the same cut: every pass that reads it posts a new message (DRN2)",
     NOTICES,
     '        if any(n["key"] == notice["key"] for n in notices):\n',
     "        if False:\n"),
    ("M4892", "a watch stopped between the closure and the state says « jamais aboutie » after « aboutie » "
     "(DRN2)", WATCH,
     '    if isinstance(said_drain, dict) and said_drain.get("status") not in (None, "pending"):\n',
     "    if False:\n"),
    ("M4893", "the state written before the closure: a closure refused (a full disk) is never said (L1A, "
     "DRN2)", WATCH,
     "    _say_closed(vm, rid, ended, elapsed, report)\n"
     '    _save_isolation_state(rid, {**state, "drain": ended, "drain_ended_at": now.isoformat()})\n',
     '    _save_isolation_state(rid, {**state, "drain": ended, "drain_ended_at": now.isoformat()})\n'
     "    _say_closed(vm, rid, ended, elapsed, report)\n"),
    ("M4894", "the webhook speaks too while the bot is configured: the closure posted twice, in the channel "
     "and in the VM's thread (DRN2)", NOTICES,
     '    if notice["via"] == "webhook":\n',
     '    if notice["via"] in ("webhook", "bot"):\n'),
    ("M4895", "a restarted bot forgets what it posted: every closure posted again in its thread (DRN2)", BOT,
     "        return {str(k) for k in json.loads(_NOTICES_POSTED_STORE.read_text())}\n",
     "        return set()\n"),
    ("M4896", "a VM released before the end of its cut: what was announced pending never closed (DRN2)",
     WATCH,
     "        if vm_notices.said(key) is None:\n",
     "        if False:\n"),
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
]
TESTS = {**{mid: _T for mid in ("M4890", "M4891", "M4892", "M4893", "M4894", "M4895", "M4896", "M4897",
                                 "M4899")},
         "M4898": _C}
