"""JUG2d (#799): without the bot, a card posted at once by `escalations._notify` is bounded as every post
of the notices (`vm_notices.post_webhook`: its own thread, `POST_DEADLINE_S`, the name's resolution
included) — one post, never queued, never posted again; `check-ttl` posts its queued card outside the
VM's lock; README, the Makefile's help, the command's help and its card say it escalates, never that it
releases; a failed post logs its exception's types, never the webhook's token (the review's round 1).
M5225–M5234 and M5260–M5262, measured by tests/unit/test_notify_bounded.py."""
NOTICES = "glorfindel/vm_notices.py"
ESC = "glorfindel/escalations.py"
REASSERT = "glorfindel/reassert.py"
CLI = "glorfindel/cli.py"
_T = "tests/unit/test_notify_bounded.py"

_POST = "        vm_notices.post_webhook(card_payload(esc), f\"card:{esc.get('id') or '?'}\", url)\n"

MUTANTS = [
    ("M5225", "a card posted at once by `requests.post(url, timeout=5)` from its caller's thread, as before "
     "JUG2d: a webhook whose name never resolves holds the graph's cycle (JUG2d)", ESC,
     _POST,
     "        import requests\n        requests.post(url, json=card_payload(esc), timeout=5)\n"),
    ("M5226", "a card posted at once with requests' own timeouts, to connect and to read, and no deadline: "
     "the name's resolution still unbounded (JUG2d)", ESC,
     _POST,
     "        import requests\n        requests.post(url, json=card_payload(esc), "
     "timeout=(vm_notices.CONNECT_TIMEOUT_S, vm_notices.READ_TIMEOUT_S))\n"),
    ("M5227", "every card queued, a lock held or not: outside the watch, a card of the console or the CLI "
     "waits for a pass that may never come (JUG2d)", ESC,
     "        if vm_notices.must_defer():\n            vm_notices.queue_card(esc)\n",
     "        if True:\n            vm_notices.queue_card(esc)\n"),
    ("M5228", "a card the webhook did not take at once queued as well: a post past the deadline that "
     "delivers, then the pass's, said twice (JUG2d)", ESC,
     _POST,
     "        if not vm_notices.post_webhook(card_payload(esc), f\"card:{esc.get('id') or '?'}\", url):\n"
     "            vm_notices.queue_card(esc)\n"),
    ("M5229", "the TTL's card posted by a relay pass under the VM's lock: an isolation of that VM waits for "
     "the webhook (JUG2d)", REASSERT,
     "                _save_isolation_state(rid, {**state, \"ttl_alerted_at\": now.isoformat()})\n",
     "                _save_isolation_state(rid, {**state, \"ttl_alerted_at\": now.isoformat()})\n"
     "                from glorfindel import vm_notices\n                vm_notices.relay_pass()\n"),
    ("M5230", "`check-ttl` runs its relay pass holding the lock of each VM it escalated: the webhook waited "
     "for under it (JUG2d)", CLI,
     "    # a card an earlier run left in the queue too.\n    _post_queued_notices()\n",
     "    # a card an earlier run left in the queue too.\n"
     "    from glorfindel.actions import _vm_lock\n"
     "    with __import__(\"contextlib\").ExitStack() as _held:\n"
     "        for a in alerts:\n"
     "            _held.enter_context(_vm_lock(a[\"vm\"]))\n"
     "        _post_queued_notices()\n"),
    ("M5231", "the TTL's card says the isolation was released at the TTL's end, though nothing is released "
     "(JUG2d, Q1)", ESC,
     "    \"ttl_exceeded\": \"isolation au-delà du TTL (à revoir, jamais levée seule)\",",
     "    \"ttl_exceeded\": \"isolation levée à l'expiration du TTL\","),
    ("M5232", "README says `check-ttl` releases isolations past the TTL (JUG2d, Q1)", "README.md",
     "# escalate isolations older than TTL (default 4h): a card each, never a release",
     "# release isolations older than TTL (default 4h)"),
    ("M5233", "the Makefile's help says `make glorfindel-check-ttl` releases expired isolations (JUG2d, Q1)",
     "Makefile",
     "Escalate expired isolations (TTL): a card each, never a release",
     "Release expired isolations (TTL)"),
    ("M5234", "`check-ttl --help` says the TTL is the age before an auto-release (JUG2d, Q1)", CLI,
     "help=\"Max isolation age in hours before its card (ttl_exceeded) — never a release. \"",
     "help=\"Max isolation age in hours before auto-release. \""),
    # The review's round 1 (M5260–M5264).
    ("M5260", "a failed post logged with its exception's text: requests writes the webhook's whole path, "
     "its token in the log (JUG2d review)", NOTICES,
     '    log.warning("notice %s: webhook unreachable (%s)", key, _error_said(exc))\n',
     '    log.warning("notice %s: webhook unreachable (%s)", key, exc)\n'),
    ("M5261", "what a failed post wraps logged by its text, not its type: the token in the log through "
     "`MaxRetryError`'s message (JUG2d review)", NOTICES,
     "        names.append(type(e).__name__)\n",
     "        names.append(str(e))\n"),
    ("M5262", "`.envrc.example` says a TTL of 0 disables it, though `ttl_alerts(0)` escalates every isolation "
     "at once (JUG2d review)", ".envrc.example",
     "# 0 ne désactive rien : toutes les isolations sont escaladées tout de suite (watch et check-ttl).",
     "# TTL : mettre 0 pour désactiver"),
]
TESTS = {mid: _T for mid, *_ in MUTANTS}
