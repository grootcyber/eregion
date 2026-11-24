"""FS1g (#1127): the restore executor apart — the restore's own queue (its domain, its verification),
the guards it replays (the card, the moment, one restore at a time, the bot's human), the second factor
absent (TOT1) that refuses every request, its refusal to start (the flag, its pair, IMDS), a stale
request never restored late, an interrupted one never run again. M7226–M7245, measured by
tests/unit/test_restore_executor.py."""
RQ = "eregion_core/restore_queue.py"
EX = "glorfindel/restore_executor.py"
APPROVAL = "glorfindel/approval.py"
_T = "tests/unit/test_restore_executor.py"

MUTANTS = [
    ("M7226", "the restore started outside the VM's claim: the CLI's restore and the executor's at once (FS1g)", EX,
     "            with jobs.restore_claim(req.resource_id):\n                job = jobs.start_restore(",
     "            if True:\n                job = jobs.start_restore("),
    ("M7227", "the second factor never asked: a restore from a button runs before TOT1 (FS1g)", EX,
     "            why = second_factor_refusal(req)\n            if why:\n",
     "            why = second_factor_refusal(req)\n            if False:\n"),
    ("M7228", "an unsigned restore request read as signed (FS1g)", RQ,
     '    if doc.get("sig") is None:\n        raise Refused("unsigned"',
     '    if False:\n        raise Refused("unsigned"'),
    ("M7229", "a restore's signature never checked: a field changed after it was signed taken (FS1g)", RQ,
     "    if not watch_key.holds(pin, DOMAIN_REQUEST, doc):\n        raise Refused(\"bad_signature\")\n", ""),
    ("M7230", "a restore request signed by another key than the one pinned for its directory taken (FS1g)", RQ,
     "    if said != want:\n        for other, key in pins.items():",
     "    if False:\n        for other, key in pins.items():"),
    ("M7231", "a restore signed under the watch's queue domain: one signature reads as both (FS1g)", RQ,
     'DOMAIN_REQUEST = "eregion.restore-request/1"\n', 'DOMAIN_REQUEST = aq.DOMAIN_REQUEST\n'),
    ("M7232", "an expired restore request taken: restored late, after an outage (FS1g)", RQ,
     "    if now >= expires:\n        raise Refused(\"expired\"", "    if False:\n        raise Refused(\"expired\""),
    ("M7233", "a restore request valid for longer than its life taken (FS1g)", RQ,
     "    if expires - issued > timedelta(seconds=MAX_LIFETIME_S):\n", "    if False:\n"),
    ("M7234", "a restore request's nonce never claimed: a request replayed restores again (FS1g)", RQ,
     "    if not fresh:\n        raise Refused(\"replayed\")\n", ""),
    ("M7235", "the restore requests of a service never bounded (FS1g)", RQ,
     "    if not rate.take(service, now):\n", "    if False:\n"),
    ("M7236", "the restore runs on the request's spelling of the VM, not the card's at the byte (FS1g)", EX,
     '        if req.resource_id != card.get("resource_id"):\n', "        if False:\n"),
    ("M7237", "a card resolved meanwhile restored all the same (FS1g)", EX,
     '        if card is None:\n            raise rq.Refused("card_not_pending"',
     '        if False:\n            raise rq.Refused("card_not_pending"'),
    ("M7238", "the card's restore guard not replayed by the executor: an anchored card restored (FS1g)", EX,
     "        why = approval.restore_refusal(card, _vm(req.resource_id))\n        if why:\n            raise _Guard(why)\n",
     ""),
    ("M7239", "the moment never read by the executor: a time without its zone restores the wrong point (FS1g)", EX,
     "            before = restore_plan.parse_moment(req.before)\n", "            before = req.before\n"),
    ("M7240", "another restore of the VM running never refuses the request (FS1g)", EX,
     "        if busy:\n            raise rq.Refused(\"restore_busy\"", "        if False:\n            raise rq.Refused(\"restore_busy\""),
    ("M7241", "the bot's human never read against the executor's copy of the allowed users (FS1g)", EX,
     '        if req.service == "bot":\n            why = approval.discord_refusal(req.by, self.environ)\n',
     '        if False:\n            why = approval.discord_refusal(req.by, self.environ)\n'),
    ("M7242", "a request whose life ended while it waited restored late (FS1g)", EX,
     "        if now >= req.expires_at:\n            return self._refuse(", "        if False:\n            return self._refuse("),
    ("M7243", "a request cut by a stop never said failed: its receipt stays accepted (FS1g)", EX,
     '            if doc is None or doc["state"] not in ("received", "accepted"):\n',
     "            if True:\n"),
    ("M7244", "the executor starts with IMDS answering its container: the watch's identity within its reach (FS1g)",
     EX, "    if (reach or imds_reachable)():\n", "    if False:\n"),
    ("M7245", "the executor starts without a whole pair of its own: DefaultAzureCredential's chain (FS1g)", EX,
     "    why = pair_problem(environ)\n    if why:\n        return why\n", ""),
]
TESTS = {f"M{n}": _T for n in range(7226, 7246)}
