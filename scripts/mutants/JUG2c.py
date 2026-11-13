"""JUG2c (#788): without the bot, neither a cut's closure nor the reassertion waits for a webhook — under a
VM's lock or in the reassertion's pass (`vm_notices.must_defer`), a notice for the webhook is queued and a
pass of the watch posts it in its own thread, at once where the watch serves the queue; a post that fails
leaves it in the queue, never given to an absent bot, its tries capped; `check-ttl`, from cron, posts what
it queued. M5135–M5144 and M5185–M5187, measured by
tests/unit/test_webhook_unwaited.py."""
NOTICES = "glorfindel/vm_notices.py"
ESC = "glorfindel/escalations.py"
REASSERT = "glorfindel/reassert.py"
CLI = "glorfindel/cli.py"
_T = "tests/unit/test_webhook_unwaited.py"

MUTANTS = [
    ("M5135", "a card written under a VM's lock or by the reassertion posted at once: the reassertion of "
     "every VM, and an isolation of that VM, wait for the webhook (JUG2c)", ESC,
     "        if vm_notices.must_defer():\n            vm_notices.queue_card(esc)\n            return\n",
     ""),
    ("M5136", "a cut's closure posted by `say` under its VM's lock, the bot not configured: an isolation of "
     "the same VM waits for the webhook, up to 10 s (JUG2c)", NOTICES,
     '    if defer and notice["via"] == "webhook":\n',
     "    if False:\n"),
    ("M5137", "the reassertion's pass, outside a VM's lock, waits for the webhook again: a card on an "
     "unreadable state holds the reassertion of every VM (JUG2c)", NOTICES,
     '    return getattr(_DEFER, "d", 0) > 0 or holds_vm_lock()\n',
     "    return holds_vm_lock()\n"),
    ("M5138", "a VM's lock no longer read: a closure or a card said under it, outside the reassertion, "
     "posts and holds the lock (JUG2c)", NOTICES,
     '    return getattr(_DEFER, "d", 0) > 0 or holds_vm_lock()\n',
     '    return getattr(_DEFER, "d", 0) > 0\n'),
    ("M5139", "the reassertion's pass no longer marked: its cards outside a VM's lock wait for the webhook "
     "(JUG2c)", REASSERT,
     "    with vm_notices.deferred():\n        return _pass(connector, autonomy)\n",
     "    return _pass(connector, autonomy)\n"),
    ("M5140", "a queued notice never posted without the bot: the closure and the card silenced, waiting "
     "for a pass that skips them (JUG2c)", NOTICES,
     '            if n.get("queued") is True:     # for the webhook, the bot not configured (JUG2c)\n',
     "            if False:\n"),
    ("M5141", "a queued notice the webhook refused given to the bot, absent: never said again (JUG2c)",
     NOTICES,
     '                    n["via"] = _back(n)     # queued: back to the queue, never to an absent bot (JUG2c)\n',
     ""),
    ("M5142", "a notice queued while a pass runs waits for the next minute: the running pass starts none "
     "at its end (JUG2c)", NOTICES,
     "        if _KICKED.is_set() and _SERVED:\n            _start_pass()",
     "        if False:\n            _start_pass()"),
    ("M5143", "a queued notice starts no pass where the watch serves the queue: said a minute late (JUG2c)",
     NOTICES,
     "    _KICKED.set()\n    if _SERVED:\n        _start_pass()\n",
     "    _KICKED.set()\n"),
    ("M5144", "a queued card posted from the store's title and text, not written as `_notify` writes it: "
     "the action, the type and the run lost from the channel (JUG2c)", NOTICES,
     '    if notice.get("kind") == CARD_KIND:\n        card = (notice.get("detail") or {}).get("card")\n',
     '    if False:\n        card = (notice.get("detail") or {}).get("card")\n'),
    # The review's round 1 (M5185–M5189).
    ("M5185", "`check-ttl` from cron no longer posts what it queued: its card, written under the VM's lock, "
     "never said to the webhook without the watch (JUG2c review)", CLI,
     "    # a card an earlier run left in the queue too.\n    _post_queued_notices()\n",
     "    # a card an earlier run left in the queue too.\n"),
    ("M5186", "a queued notice's tries uncapped: a webhook in 500 gets the card at every pass for 24 h "
     "(JUG2c review)", NOTICES,
     '    if n.get("via") != OUTBOX or _tries(n) >= RELAY_MAX_TRIES:\n',
     '    if n.get("via") != OUTBOX:\n'),
    ("M5187", "at the cap, a queued notice said to wait for a bot that is not there (JUG2c review)", NOTICES,
     '    if n["tries"] == RELAY_MAX_TRIES and n.get("queued") is True:\n',
     "    if False:\n"),
]
TESTS = {mid: _T for mid, *_ in MUTANTS}
