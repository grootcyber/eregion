"""SEC-B (#634, audit du 06/11 — V-06, V-08, V-09, V-10, V-12): the signed action queue ready to be
turned on. A proposal signed again only from what the watch holds, the target that runs the one it
signed and compared at the byte, a relève that never freezes (a bounded wait list, in priority), the
registers under a lock between processes and one watch per HOME, a line of the escalations' store
that is not a card failing nothing. M5426–M5445, measured by tests/unit/test_action_proposal.py,
test_action_queue_watch.py and test_locks.py."""
AQ = "eregion_core/action_queue.py"
QW = "glorfindel/queue_watch.py"
ESC = "glorfindel/escalations.py"
CLI = "glorfindel/cli.py"
_PROPOSAL = "tests/unit/test_action_proposal.py"
_WATCH = "tests/unit/test_action_queue_watch.py"
_LOCKS = "tests/unit/test_locks.py"

MUTANTS = [
    # ── V-06: signed again from the watch's state only ─────────────────────────────────
    ("M5426", "a refresh signs the proposal again from the card as the store gives it (SEC-B, V-06)", ESC,
     "        fields = _held(e) if decision is None else decision\n",
     "        fields = action_queue.card_fields(e) if decision is None else decision\n"),
    ("M5427", "the watch remembers its proposals by the signal's id, which anyone can predict (SEC-B, V-06)", ESC,
     '    return str(e.get("id") or "")\n\n\ndef _held',
     '    return str(e.get("signal_id") or "")\n\n\ndef _held'),
    ("M5428", "a card that no longer carries the watch's proposal signed again all the same (SEC-B, V-06)", ESC,
     "    if kept is None or not isinstance(proposal, dict) or action_queue.digest(proposal) != kept[0]:\n",
     "    if kept is None:\n"),
    ("M5429", "a decision folded into a card signs the port the card holds, not its own (SEC-B, §2.4)", ESC,
     "                if _propose(e, _decision(action, resource_id, escalation_type, action_params)):\n",
     '                if _propose(e, _decision(action, resource_id, escalation_type, e.get("action_params"))):\n'),
    # ── V-08: the target signed, compared at the byte ─────────────────────────────────
    ("M5430", "the target that runs taken from the request, not from the proposal signed (SEC-B, V-08)", QW,
     "            req = _signed_target(req, proposal)                  # SEC-B: what runs is what was signed\n",
     ""),
    ("M5431", "the request and the proposal compared after lower() (SEC-B, V-08)", AQ,
     '    if request.resource_id != proposal["resource_id"]:\n',
     '    if request.resource_id.lower() != str(proposal["resource_id"]).lower():\n'),
    ("M5432", "an identifier out of ASCII taken (SEC-B, V-08)", AQ,
     "        if not value.isascii():\n", "        if False:\n"),
    # ── V-09: the relève never freezes ─────────────────────────────────────────────────
    ("M5433", "judging waits for an execution to come free (SEC-B, V-09)", QW,
     "        self._backlog.put_nowait((_priority(req.verb), next(self._arrival), item))\n",
     '        while self.busy()["running"] >= IN_FLIGHT:\n            time.sleep(0.05)\n'
     "        self._backlog.put_nowait((_priority(req.verb), next(self._arrival), item))\n"),
    ("M5434", "the status not written again while every execution is taken (SEC-B, V-09)", QW,
     "            self.status(now or datetime.now(timezone.utc))\n",
     '            if self.busy()["running"] < IN_FLIGHT:\n                self.status(now or datetime.now(timezone.utc))\n'),
    ("M5435", "a lift passes before a containment in the wait list (SEC-B, V-09)", QW,
     "    return 0 if verb in CONTAIN else 1\n", "    return 0\n"),
    ("M5436", "a request whose life ended while it waited run late (SEC-B, V-09)", QW,
     "            if now >= req.expires_at:\n", "            if False:\n"),
    # ── V-10: between processes ────────────────────────────────────────────────────────
    ("M5437", "the register of nonces claimed without its lock between processes (SEC-B, V-10)", AQ,
     "        with self._lock, _between_processes(self.path):\n            try:\n                seen = self._read()\n",
     "        with self._lock:\n            try:\n                seen = self._read()\n"),
    ("M5438", "the register of proposals consumed without its lock between processes (SEC-B, V-10)", AQ,
     "        with self._lock, _between_processes(self.path):\n            done = self._read()\n",
     "        with self._lock:\n            done = self._read()\n"),
    ("M5439", "a second watch on the same HOME picks the queue up (SEC-B, V-10)", QW,
     "    hold = hold_the_queue()\n", "    hold = None\n"),
    # ── V-12: a line of the store that is not a card ───────────────────────────────────
    ("M5440", "pending raises on a line of the store that is not a card (SEC-B, V-12)", ESC,
     "        e = _card_of(line)              # SEC-B: a line that is not a card passed over, said once\n"
     '        if e is not None and e.get("status") == "pending":\n',
     '        e = json.loads(line)\n        if e.get("status") == "pending":\n'),
    ("M5441", "resolve loses the line that is not a card when it rewrites the store (SEC-B, V-12)", ESC,
     "        if e is None:                   # SEC-B: kept as it is, never lost, never a failure\n"
     "            updated.append(line)\n            continue\n        if e.get(\"id\") == escalation_id:\n",
     "        if e is None:                   # SEC-B: kept as it is, never lost, never a failure\n"
     "            continue\n        if e.get(\"id\") == escalation_id:\n"),
    ("M5442", "resolve_by_resource raises on a line of the store that is not a card (SEC-B, V-12)", ESC,
     "        e = _card_of(line)\n        if e is None:                   # SEC-B: kept as it is, never lost, never a failure\n"
     "            updated.append(line)\n            continue\n        if (\n",
     "        e = json.loads(line)\n        if (\n"),
    ("M5443", "an action done says failed when its card cannot be settled (SEC-B, V-12)", QW,
     "        try:\n            from glorfindel import escalations\n"
     "            escalations.resolve(card[\"id\"], note=\"exécutée par la file d'actions (FS1b)\")\n"
     "        except Exception as exc:\n",
     "        if True:\n            from glorfindel import escalations\n"
     "            escalations.resolve(card[\"id\"], note=\"exécutée par la file d'actions (FS1b)\")\n"
     "        if False:\n            exc = None\n"),
    # ── V-09, V-10: the wait list bounded, the watch command refused ───────────────────
    ("M5444", "the wait list unbounded: a request accepted whatever waits already (SEC-B, V-09)", QW,
     "            if not self.inline and self._backlog.qsize() >= BACKLOG:\n", "            if False:\n"),
    ("M5445", "the watch command runs on beside another watch of the same HOME (SEC-B, V-10)", CLI,
     "        console.print(f\"[red]Watch refusée :[/red] {_esc_markup(str(exc))}\")\n        sys.exit(1)\n",
     "        console.print(f\"[red]Watch refusée :[/red] {_esc_markup(str(exc))}\")\n"),
]
TESTS = {f"M{n}": _WATCH for n in range(5426, 5446)}
TESTS.update({mid: _PROPOSAL for mid in ("M5426", "M5427", "M5428", "M5429")})
TESTS.update({"M5432": f"{_WATCH} tests/unit/test_action_queue.py", "M5437": _LOCKS, "M5438": _LOCKS,
              "M5439": f"{_WATCH} {_LOCKS}"})
