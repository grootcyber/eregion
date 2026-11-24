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

# Jonathan's answers of 24/11: the restore's own flag, the vault's running restore read before anything,
# the principal in Imladris's Terraform. M7272–M7279.
JOBS = "glorfindel/providers/azure/restore_jobs.py"
CONN = "glorfindel/providers/azure/connector.py"
BOTR = "glorfindel/bot_restore.py"
RESTORE = "glorfindel/providers/azure/restore.py"
TF = "infra/glorfindel-host/restore_executor.tf"
VARS = "infra/glorfindel-host/variables.tf"
MUTANTS += [
    ("M7272", "the restore follows the action queue's flag: switched on by FS1c, today's Restore button changes (FS1g)",
     RQ, 'FLAG_ENV = "EREGION_RESTORE_QUEUE"\n', 'FLAG_ENV = "EREGION_ACTION_QUEUE"\n'),
    ("M7273", "the vault's running restore never read: a second restore of a VM started elsewhere (FS1g)", RESTORE,
     "        restore_jobs.refuse_if_running(backup_client, vault, v_rg, rg, vm_name, manual=lambda: restore_jobs.by_hand(\n",
     "        (lambda *a, **k: None)(backup_client, vault, v_rg, rg, vm_name, manual=lambda: restore_jobs.by_hand(\n"),
    ("M7274", "the vault's running restore said as a failure of the executor, not a refusal (FS1g)", EX,
     '                state, code, reason = "refused", "vault_job_running", _masked(exc, REASON_CHARS)\n',
     '                state, code, reason = "failed", "vault_job_running", _masked(exc, REASON_CHARS)\n'),
    ("M7275", "a finished restore of the VM taken for one running: every restore refused after the first (FS1g)",
     JOBS, '        if str(getattr(p, "status", "") or "").lower() in RUNNING:\n', "        if True:\n"),
    ("M7276", "another group's VM of the same name counted: its restore refuses this one (FS1g)", JOBS,
     "        if container and not container.endswith(want):\n            continue\n", ""),
    ("M7277", "the vault's jobs unreadable, the refusal never said as such (FS1g)", JOBS,
     "        jobs = running(client, vault, v_rg, vm_rg, vm_name)\n    except Exception as exc:\n",
     "        jobs = running(client, vault, v_rg, vm_rg, vm_name)\n    except ZeroDivisionError as exc:\n"),
    ("M7278", "the executor's principal never among restore_principals: no neutralization, no staging keys (FS1g)", TF,
     "  var.restore_executor_enabled ? { executor = azuread_service_principal.restore_executor[0].object_id } : {})\n",
     "  {})\n"),
    ("M7279", "the restore principal created by default, without Jonathan's plan (FS1g)", VARS,
     "  type        = bool\n  default     = false\n}\n\nvariable \"restore_executor_certificate\"",
     "  type        = bool\n  default     = true\n}\n\nvariable \"restore_executor_certificate\""),
]

# The review of 24/11 (Jonathan's points 5 and 6, and the reviewer's). M7280–M7281, M7320–M7324.
MUTANTS += [
    ("M7280", "the vault's jobs unreadable, the refusal never says how to restore by hand (FS1g)", JOBS,
     '                said = "\\n" + manual()\n', '                said = ""\n'),
    ("M7281", "the restore executor takes DefaultAzureCredential's chain, the VM's managed identity in it (FS1g)",
     CONN, '            credential = getattr(self, "explicit_credential", None) or DefaultAzureCredential()\n',
     "            credential = DefaultAzureCredential()\n"),
    ("M7320", "a card acknowledged while the request waited restored all the same (FS1g)", EX,
     "            self._attach(req)                        # the card read again at its turn\n", "            pass\n"),
    ("M7321", "a judge that breaks leaves its receipt « received » for ever (FS1g)", EX,
     '            return self._receipt(service, request_id, "failed", request=req, reason=reason, now=now)\n',
     "            raise\n"),
    ("M7322", "the bot says `glorfindel restore` when it deposits a request (FS1g)", BOTR,
     '            if rq.enabled() else "")\n', '            if False else "")\n'),
    ("M7323", "Reader not given to the executor on the groups of Restore: the vault's jobs never read (FS1g)", TF,
     '  role_definition_name = "Reader"\n', '  role_definition_name = "Restore Reader"\n'),
    ("M7324", "the refusal of the vault cut on the card: the command to restore by hand lost (FS1g)", EX,
     '                state, code, reason = "refused", "vault_job_running", _masked(exc, REASON_CHARS)\n',
     '                state, code, reason = "refused", "vault_job_running", _masked(exc)\n'),
]
TESTS = {f"M{n}": _T for n in [*range(7226, 7246), *range(7272, 7282), *range(7320, 7325)]}
