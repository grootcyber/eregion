"""FS1g (#1127, docs/design/file-actions-signee.md, Q2): the restore executor — the restore's own queue
(eregion_core/restore_queue.py), its verification, the guards it replays, its refusal to start, and
the console's and the bot's deposits.

The keys come from fixed seeds: never a real key. A throwaway HOME, runs/ in tmp, no Azure (a
connector that records what it is asked, and refuses anything but the restore), no network (IMDS is a
fake connect), no model. The oracles are the receipts the executor signs and the calls the connector
saw — never the code's markers (A0). Mutants M7226–M7245 (scripts/mutants/FS1g.py) are measured here.
"""
from __future__ import annotations

import asyncio
import json
import os
from datetime import datetime, timedelta, timezone

import pytest

import eregion_core.action_queue as aq
import eregion_core.restore_queue as rq
import eregion_core.watch_key as watch_key
from glorfindel import approval, escalations, jobs, queue_watch, restore_executor

EXECUTOR = watch_key.Signer(bytes(range(160, 192)))
CONSOLE = watch_key.Signer(bytes(range(40, 72)))
BOT = watch_key.Signer(bytes(range(80, 112)))
STRANGER = watch_key.Signer(bytes(range(120, 152)))
PINS = {"console": CONSOLE.public, "bot": BOT.public}
SIGNERS = {"console": CONSOLE, "bot": BOT}
SUB = "00000000-0000-0000-0000-0000000000cc"
VM = f"/subscriptions/{SUB}/resourceGroups/rg-example-a/providers/Microsoft.Compute/virtualMachines/vm-example-01"
BEFORE = "2026-10-29T08:00:00+00:00"
DISCORD = {"via": "discord", "user": "111", "name": "an operator"}
ALLOWED = {"DISCORD_ALLOWED_USERS": "111"}


class Connector:
    """What the executor may call on Azure — the restore, recorded; anything else raises (the
    executor isolates nothing, blocks nothing, writes no configuration)."""

    def __init__(self, fail: Exception | None = None):
        self.calls: list[tuple] = []
        self.fail = fail

    def restore_from_backup(self, resource_id, **kw):
        self.calls.append((resource_id, kw))
        if self.fail:
            raise self.fail
        return {"job_name": "job-0001", "rg": "rg-example-a", "recovery_point": "rp-1",
                "recovery_point_time": "2026-10-29T07:00:00+00:00", "recovery_point_vault_tier": True}

    def __getattr__(self, name):
        raise AssertionError(f"the restore executor called {name} on Azure")


@pytest.fixture
def world(tmp_path, monkeypatch):
    for var in ("DISCORD_ALLOWED_USERS", "DISCORD_ALLOWED_ROLES", "GLORFINDEL_WEBHOOK_URL", "DISCORD_BOT_TOKEN"):
        monkeypatch.delenv(var, raising=False)
    monkeypatch.setenv("GLORFINDEL_BACKUP_VAULT", "rsv-example")
    monkeypatch.chdir(tmp_path)
    conn = Connector()
    said: list[str] = []
    ex = restore_executor.RestoreExecutor(EXECUTOR, conn, root=tmp_path / "runs", pins=PINS, say=said.append,
                                          inline=True, environ=ALLOWED, seen=aq.MemorySeen())
    return {"ex": ex, "conn": conn, "root": tmp_path / "runs", "said": said, "tmp": tmp_path}


@pytest.fixture
def second_factor(monkeypatch):
    """TOT1 stood in for: the operator's code taken as given — to reach the restore behind it."""
    monkeypatch.setattr(restore_executor, "second_factor_refusal", lambda req: "")


def _card(**kw) -> dict:
    fields = {"signal_id": "rule-ransomware-0123abcd", "resource_id": VM, "action": "restore_from_backup",
              "escalation_type": "destructive_action", "reason": "restore needs a human", "ttp": "T1486", **kw}
    cid = escalations.record(**fields)
    return next(e for e in escalations.all_escalations() if e["id"] == cid)


def _ask(w, card, *, service="console", signer=None, resource_id=None, before=BEFORE, by=None, now=None,
         lifetime_s=rq.MAX_LIFETIME_S, nonce=None) -> dict:
    doc = rq.new_request(signer or SIGNERS[service], service=service,
                         resource_id=resource_id if resource_id is not None else card["resource_id"],
                         card=card["id"], before=before, now=now, lifetime_s=lifetime_s, nonce=nonce,
                         by=by if by is not None else (DISCORD if service == "bot" else
                                                       {"via": "console-token", "session": "0a1b2c3d"}))
    _write(w, service, doc)
    return doc


def _write(w, service, doc) -> None:
    d = rq.request_dir(service, w["root"])
    d.mkdir(parents=True, exist_ok=True)
    (d / f"{doc['id']}.json").write_text(json.dumps(doc))


def _receipt(w, doc, service=None) -> dict:
    got, why = rq.receipt_said(service or doc["service"], doc["id"], root=w["root"], public=EXECUTOR.public)
    assert got is not None, why or "no receipt"
    return got


def _code(w, doc) -> str:
    r = _receipt(w, doc)
    assert r["state"] == "refused", r
    return r["code"]


# ── From end to end ──────────────────────────────────────────────────────────────────

def test_a_restore_signed_deposited_picked_up_and_started_once(world, second_factor):
    """M7226: the request verified, its card's guards replayed, the restore started under the claim,
    the receipt says it — the connector asked the restore once, of the card's VM, before the moment."""
    card = _card()
    doc = _ask(world, card)
    world["ex"].poll()
    r = _receipt(world, doc)
    assert r["state"] == "done" and r["result"]["status"] == "started", r
    assert r["result"]["restore_job_name"] == "job-0001"
    assert [c[0] for c in world["conn"].calls] == [VM]
    assert world["conn"].calls[0][1]["before_attack_time"] == BEFORE
    assert world["conn"].calls[0][1]["vault"] == "rsv-example"
    assert jobs.get_job(VM)["status"] == "InProgress"        # followed as any other restore
    assert jobs.restore_in_progress(VM)                       # one at a time, from now on
    world["ex"].poll()                                        # never judged twice
    assert len(world["conn"].calls) == 1


def test_until_tot1_every_restore_from_a_button_is_refused_and_said(world):
    """M7227: no second factor yet (TOT1, #685) — refused, the reason said, Azure never asked."""
    doc = _ask(world, _card())
    world["ex"].poll()
    assert _code(world, doc) == "second_factor"
    assert "TOT1" in _receipt(world, doc)["reason"]
    assert world["conn"].calls == []
    status = json.loads((rq.receipts_dir(world["root"]) / rq.STATUS_NAME).read_text())
    assert "TOT1" in status["second_factor"] and not rq.executor_refusal(status, "status", EXECUTOR.public)


def test_the_receipt_is_signed_by_the_executor_under_its_own_domain(world):
    doc = _ask(world, _card())
    world["ex"].poll()
    r = _receipt(world, doc)
    assert not rq.executor_refusal(r, "receipt", EXECUTOR.public)
    assert not watch_key.holds(EXECUTOR.public, aq.DOMAIN_QUEUE, r)     # never reads as the watch's
    assert rq.receipt_said("console", doc["id"], root=world["root"], public=STRANGER.public)[0] is None


# ── The verification, refused before anything ──────────────────────────────────────

def _refused_before_azure(w, doc, code):
    w["ex"].poll()
    assert _code(w, doc) == code
    assert w["conn"].calls == []


def test_unsigned_refused_and_a_critical_card(world, second_factor):
    """M7228"""
    doc = _ask(world, _card())
    doc.pop("sig")
    _write(world, "console", doc)
    _refused_before_azure(world, doc, "unsigned")
    assert [e for e in escalations.pending() if e["escalation_type"] == "queue_tampered"]


def test_a_field_changed_after_the_signature_is_refused(world, second_factor):
    """M7229: the moment changed after the console signed — bad_signature."""
    doc = _ask(world, _card())
    doc["before"] = "2026-10-01T08:00:00+00:00"
    _write(world, "console", doc)
    _refused_before_azure(world, doc, "bad_signature")


def test_another_key_is_refused_and_the_other_services_key_is_wrong_service(world, second_factor):
    """M7230"""
    card = _card()
    _refused_before_azure(world, _ask(world, card, signer=STRANGER), "unknown_key")
    doc = rq.new_request(BOT, service="console", resource_id=VM, card=card["id"], before=BEFORE)
    _write(world, "console", doc)
    _refused_before_azure(world, doc, "wrong_service")


def test_a_service_without_its_key_pinned_is_refused(world, second_factor):
    world["ex"].pins = {"bot": BOT.public}
    _refused_before_azure(world, _ask(world, _card()), "no_key_pinned")


def test_a_request_of_the_watchs_queue_never_reads_as_a_restore(world, second_factor):
    """M7231: the domains apart — an action request's signature never holds for a restore, nor the
    reverse; a restore request with the action queue's fields is not one."""
    card = _card()
    body = {k: v for k, v in rq.new_request(CONSOLE, service="console", resource_id=VM, card=card["id"],
                                            before=BEFORE).items() if k != "sig"}
    body["sig"] = CONSOLE.sign(aq.DOMAIN_REQUEST, body)
    _write(world, "console", body)
    _refused_before_azure(world, body, "bad_signature")
    act = aq.new_request(CONSOLE, service="console", verb="reset", resource_id=VM)
    _write(world, "console", act)
    _refused_before_azure(world, act, "malformed")


def test_the_time_is_held(world, second_factor):
    """M7232, M7233: expired, issued ahead, valid too long."""
    card, now = _card(), datetime.now(timezone.utc)
    _refused_before_azure(world, _ask(world, card, now=now - timedelta(seconds=300)), "expired")
    _refused_before_azure(world, _ask(world, card, now=now + timedelta(seconds=120)), "not_yet_valid")
    _refused_before_azure(world, _ask(world, card, lifetime_s=rq.MAX_LIFETIME_S + 60), "too_long")


def test_a_replayed_nonce_is_refused(world, second_factor):
    """M7234: the same request deposited twice (after its first receipt was swept)."""
    card = _card()
    doc = _ask(world, card)
    world["ex"].poll()
    assert _receipt(world, doc)["state"] == "done"
    jobs.save_job(VM, {**jobs.get_job(VM), "status": "Completed"})
    for claim in jobs._JOBS_DIR.glob("*.restore-claim"):
        claim.unlink()
    rq.receipt_path("console", doc["id"], world["root"]).unlink()
    world["ex"]._judged.clear()
    world["ex"].poll()
    assert _code(world, doc) == "replayed"
    assert len(world["conn"].calls) == 1


def test_the_rate_bounds_a_service(world):
    """M7235"""
    card = _card()
    docs = [_ask(world, card) for _ in range(rq.RATE_PER_MIN + 1)]
    world["ex"].poll()
    world["ex"].poll()
    codes = [_code(world, d) for d in docs]
    assert codes.count("rate_limited") == 1


def test_an_identifier_out_of_ascii_is_refused(world, second_factor):
    _refused_before_azure(world, _ask(world, _card(), resource_id=VM.replace("rg-example-a", "rg-exаmple-a")),
                          "not_ascii")


def test_a_register_that_cannot_be_kept_refuses(world, second_factor):
    class Broken:
        def claim(self, *a):
            raise OSError("disk full")
    world["ex"].seen = Broken()
    _refused_before_azure(world, _ask(world, _card()), "seen_store_unavailable")


# ── The card, the guards ─────────────────────────────────────────────────────────────

def test_the_restore_runs_on_its_cards_vm_named_at_the_byte(world, second_factor):
    """M7236: the request naming the card's VM in another case is refused — the restore runs on the card's."""
    card = _card()
    _refused_before_azure(world, _ask(world, card, resource_id=VM.replace("rg-example-a", "RG-EXAMPLE-A")),
                          "card_mismatch")


def test_a_card_resolved_meanwhile_is_refused(world, second_factor):
    """M7237"""
    card = _card()
    escalations.resolve(card["id"])
    _refused_before_azure(world, _ask(world, card), "card_not_pending")


@pytest.mark.parametrize("kw", [{"escalation_type": "control_plane_change"}, {"action": "snapshot"}])
def test_a_card_that_holds_no_restore_or_an_anchored_one_is_refused(world, second_factor, kw):
    """M7238: the console's own guard, replayed."""
    _refused_before_azure(world, _ask(world, _card(**kw)), "guard")


def test_another_vms_card_is_refused(world, second_factor):
    other = VM.replace("vm-example-01", "vm-example-02")
    _refused_before_azure(world, _ask(world, _card(), resource_id=other), "guard")


@pytest.mark.parametrize("before", ["2026-10-29T08:00:00", "2999-01-01T00:00:00+00:00", ""])
def test_a_moment_without_its_zone_or_ahead_is_refused(world, second_factor, before):
    """M7239: SEC4c, RTZ1 — never guessed, never the newest point."""
    _refused_before_azure(world, _ask(world, _card(), before=before), "guard")


def test_no_vault_configured_is_refused(world, second_factor, monkeypatch):
    monkeypatch.delenv("GLORFINDEL_BACKUP_VAULT", raising=False)
    _refused_before_azure(world, _ask(world, _card()), "guard")


def test_another_restore_of_the_vm_running_refuses_this_one(world, second_factor):
    """M7240: the CLI's own claim — a restore the CLI runs on this host refuses the request."""
    card = _card()
    with jobs.restore_claim(VM):
        _refused_before_azure(world, _ask(world, card), "restore_busy")


def test_the_claim_taken_between_the_acceptance_and_the_run_fails_it(world, second_factor):
    """The CLI took the VM after the request was accepted: failed, never two restores."""
    card = _card()
    world["ex"].inline = False
    doc = _ask(world, card)
    real = world["ex"]._serve
    world["ex"]._serve = lambda: None
    world["ex"].poll()
    assert _receipt(world, doc)["state"] == "accepted"
    with jobs.restore_claim(VM):
        item = world["ex"]._backlog.get_nowait()
        world["ex"]._take(item)
    assert _receipt(world, doc)["code"] == "restore_busy" and world["conn"].calls == []
    world["ex"]._serve = real


def test_the_bots_human_is_read_against_the_executors_copy(world, second_factor):
    """M7241: a user the executor's copy of DISCORD_ALLOWED_USERS does not list is refused."""
    card = _card()
    _refused_before_azure(world, _ask(world, card, service="bot", by={**DISCORD, "user": "999"}), "guard")
    doc = _ask(world, card, service="bot")
    world["ex"].poll()
    assert _receipt(world, doc)["state"] == "done"


def test_a_request_whose_life_ended_while_it_waited_is_never_restored_late(world, second_factor):
    """M7242: no_slot — a stale request during an outage is refused, never run late."""
    card = _card()
    world["ex"].inline = False
    world["ex"]._serve = lambda: None
    doc = _ask(world, card)
    world["ex"].poll()
    item = world["ex"]._backlog.get_nowait()
    world["ex"]._take(item, now=datetime.now(timezone.utc) + timedelta(seconds=rq.MAX_LIFETIME_S + 5))
    assert _code(world, doc) == "no_slot" and world["conn"].calls == []


def test_a_stop_between_the_claim_and_the_end_is_said_failed_never_run_again(world, second_factor):
    """M7243: recover — a receipt left accepted is failed (interrupted), never restored again."""
    card = _card()
    world["ex"].inline = False
    world["ex"]._serve = lambda: None
    doc = _ask(world, card)
    world["ex"].poll()
    fresh = restore_executor.RestoreExecutor(EXECUTOR, world["conn"], root=world["root"], pins=PINS,
                                             say=world["said"].append, inline=True, seen=aq.MemorySeen())
    assert fresh.recover() == 1
    r = _receipt(world, doc)
    assert (r["state"], r["code"]) == ("failed", "interrupted")
    fresh.poll()
    assert world["conn"].calls == []


def test_a_failed_restore_says_it_masked(world, second_factor):
    world["conn"].fail = RuntimeError(f"vault refused on /subscriptions/{SUB}/x")
    doc = _ask(world, _card())
    world["ex"].poll()
    r = _receipt(world, doc)
    assert r["state"] == "failed" and SUB not in r["reason"]
    assert not jobs.restore_in_progress(VM)          # the claim given back


# ── The start ────────────────────────────────────────────────────────────────────────

FULL = {rq.FLAG_ENV: "1", "AZURE_CLIENT_ID": "a", "AZURE_TENANT_ID": "t", "AZURE_CLIENT_SECRET": "s"}


def test_the_executor_starts_only_with_the_flag_its_pair_and_imds_cut():
    """M7244, M7245"""
    cut, open_ = (lambda: False), (lambda: True)
    assert restore_executor.startup_refusal(FULL, cut) == ""
    assert "EREGION_RESTORE_QUEUE" in restore_executor.startup_refusal({**FULL, rq.FLAG_ENV: ""}, cut)
    assert "AZURE_CLIENT_SECRET" in restore_executor.startup_refusal({**FULL, "AZURE_CLIENT_SECRET": ""}, cut)
    assert "AZURE_CLIENT_ID" in restore_executor.startup_refusal({**FULL, "AZURE_CLIENT_ID": " "}, cut)
    cert = {**FULL, "AZURE_CLIENT_SECRET": "", "AZURE_CLIENT_CERTIFICATE_PATH": "/k.pem"}
    assert restore_executor.startup_refusal(cert, cut) == ""
    assert "169.254.169.254" in restore_executor.startup_refusal(FULL, open_)
    said = restore_executor.startup_refusal({**FULL, "AZURE_CLIENT_SECRET": "a-secret-value"}, open_)
    assert "a-secret-value" not in said


def test_imds_is_reachable_only_when_a_connection_opens():
    class Conn:
        closed = False

        def close(self):
            Conn.closed = True

    def refused(addr, timeout):
        raise ConnectionRefusedError()

    def slow(addr, timeout):
        raise TimeoutError()
    assert restore_executor.imds_reachable(connect=lambda addr, timeout: Conn()) and Conn.closed
    assert not restore_executor.imds_reachable(connect=refused)
    assert not restore_executor.imds_reachable(connect=slow)


def test_main_refuses_to_start_and_says_why(monkeypatch, capsys):
    monkeypatch.delenv(rq.FLAG_ENV, raising=False)
    assert restore_executor.main([]) == 1
    assert "EREGION_RESTORE_QUEUE" in capsys.readouterr().err


def test_one_executor_per_home(tmp_path):
    fd = restore_executor.hold(tmp_path / "x")
    try:
        with pytest.raises(restore_executor.SecondExecutor):
            restore_executor.hold(tmp_path / "x")
    finally:
        os.close(fd)


# ── The watch never restores ───────────────────────────────────────────────────────────

def test_the_watch_never_takes_a_restore(world):
    """SEC7: the restore in none of the watch's verbs; a restore request in the console's directory
    is never read by the watch's queue."""
    assert not any("restore" in v for v in aq.VERBS)
    doc = _ask(world, _card())
    watch = queue_watch.QueueWatch(watch_key.Signer(bytes(range(32))), Connector(), root=world["root"],
                                   pins=PINS, say=lambda m: None, inline=True, seen=aq.MemorySeen(),
                                   read_only=False)
    watch.poll()
    assert not aq.receipt_path("console", doc["id"], world["root"]).exists()


def test_the_executor_and_the_console_refuse_the_same_cards():
    """The executor's replay (approval.restore_refusal) is the console's guard (api._restore_refusal)."""
    from eregion_console import api
    from glorfindel import bot
    assert approval.ANCHORED_TYPES == frozenset(api._ANCHORED_TYPES) == frozenset(bot._ANCHORED_TYPES)
    for kw in ({}, {"escalation_type": "control_plane_change"}, {"escalation_type": "identity_change"},
               {"action": "snapshot"}, {"resource_id": VM.replace("vm-example-01", "vm-example-02")}):
        card = _card(**kw)
        console_says, _ = api._restore_refusal(card["id"], "vm-example-01")
        assert (console_says is None) == (approval.restore_refusal(card, "vm-example-01") is None), kw


# ── The console and the bot deposit ─────────────────────────────────────────────────────

def test_the_console_deposits_with_the_queue_on_and_its_card_says_the_refusal(world, monkeypatch):
    from eregion_console import api, restore_requests
    monkeypatch.setenv(rq.FLAG_ENV, "1")
    monkeypatch.setattr(api, "_RUNS", world["root"])
    ran = []
    monkeypatch.setattr(api, "_bg_restore", lambda *a: ran.append(a))
    world["ex"].pins = {"console": aq.load_service_key("console").public}     # its key, drawn in tmp
    card = _card()
    out = asyncio.run(api.action_restore("vm-example-01", {"escalation": card["id"], "before": BEFORE}))
    assert out["status"] == "requested" and out["via"] == "restore-queue" and ran == []
    assert [r["vm_name"] for r in api._active_restores()] == ["vm-example-01"]
    world["ex"].poll()                                    # refused: no TOT1
    assert restore_requests.settle(root=world["root"], noted=api._note_restore_failure, done=api._restore_done) == 1
    assert "second_factor" in api._restore_failures()[card["id"]]["error"]
    assert api._active_restores() == []
    assert rq.waiting("console", world["root"]) == []


def test_without_the_flag_the_console_restores_as_before(world, monkeypatch):
    from eregion_console import api
    monkeypatch.setattr(api, "_RUNS", world["root"])

    async def bg(*a):
        return None
    monkeypatch.setattr(api, "_bg_restore", bg)
    card = _card()
    out = asyncio.run(api.action_restore("vm-example-01", {"escalation": card["id"], "before": BEFORE}))
    assert out["status"] == "started" and rq.waiting("console", world["root"]) == []


def test_the_bot_deposits_follows_and_says_the_receipt(world, monkeypatch):
    from glorfindel import bot_restore
    monkeypatch.setenv(rq.FLAG_ENV, "1")
    assert bot_restore.arun(_card(), BEFORE, type("I", (), {"user": None, "channel": None})()) is not None
    monkeypatch.delenv(rq.FLAG_ENV)
    assert bot_restore.arun(_card(), BEFORE, None) is None

    class User:
        id, display_name = 111, "an operator"

    class Channel:
        def __init__(self):
            self.sent = []

        async def send(self, text):
            self.sent.append(text)
            world["ex"].poll()

    card, channel = _card(), Channel()
    world["ex"].pins = {"bot": aq.load_service_key("bot").public}
    monkeypatch.setattr(rq, "receipts_dir", lambda root=None, _r=rq.receipts_dir: _r(world["root"]))
    monkeypatch.setattr(rq, "request_dir", lambda s, root=None, _r=rq.request_dir: _r(s, world["root"]))
    code, text = asyncio.run(bot_restore.ask(card, BEFORE, User(), channel, poll_s=0))
    assert code == 1 and "second_factor" in text
    assert any("déposée" in s for s in channel.sent)
    assert rq.waiting("bot", world["root"]) == []


# ── The restore's own flag, apart from the action queue's (Jonathan, 24/11) ─────────────

@pytest.mark.parametrize("action_queue,restore_queue", [("1", ""), ("", "1"), ("1", "1"), ("", "")])
def test_the_restore_follows_its_own_flag_whatever_the_action_queues(world, monkeypatch, action_queue,
                                                                     restore_queue):
    """M7272: the action queue switched on (FS1c) never changes today's Restore button; the restore's
    flag alone sends it to the executor — the console, the bot and the executor alike."""
    from eregion_console import api
    from glorfindel import bot_restore
    for var, value in ((aq.FLAG_ENV, action_queue), (rq.FLAG_ENV, restore_queue)):
        if value:
            monkeypatch.setenv(var, value)
        else:
            monkeypatch.delenv(var, raising=False)
    monkeypatch.setattr(api, "_RUNS", world["root"])

    async def bg(*a):
        return None
    monkeypatch.setattr(api, "_bg_restore", bg)
    out = asyncio.run(api.action_restore("vm-example-01", {"escalation": _card()["id"], "before": BEFORE}))
    deposited = bool(rq.waiting("console", world["root"]))
    assert deposited == (restore_queue == "1") and out["status"] == ("requested" if restore_queue else "started")
    env = {**FULL, aq.FLAG_ENV: action_queue, rq.FLAG_ENV: restore_queue}
    assert (restore_executor.startup_refusal(env, lambda: False) == "") == (restore_queue == "1")
    interaction = type("I", (), {"user": None, "channel": None})()
    assert (bot_restore.arun(_card(), BEFORE, interaction) is not None) == (restore_queue == "1")


# ── A restore the vault runs already, started elsewhere (Jonathan, 24/11) ───────────────

def _vault_world(monkeypatch):
    from glorfindel.actions import AzureConnector

    from .fake_azure import FakeAzure
    f = FakeAzure()
    nsg = f.add_nsg("rg-app", "nsg-web")
    sub = f.add_subnet("rg-net", "vnet", "app", nsg)
    vm = f.add_vm("rg-app", "web", [{"rg": "rg-app", "name": "web-nic", "ips": ["10.0.1.4"], "subnet": sub,
                                     "nsg": nsg}])
    c = AzureConnector(dry_run=False, read_only=False)
    c._network, c._compute, c._backup = f.network, f.compute, f.backup
    c._subscription_id = "s"
    import azure.mgmt.recoveryservicesbackup as rsb
    monkeypatch.setattr(rsb, "RecoveryServicesBackupClient", lambda *a, **k: f.backup)
    return f, c, vm


def test_a_restore_the_vault_runs_already_refuses_before_anything(monkeypatch):
    """M7273: on the in-memory Azure — a restore of the VM in progress in the vault (a `make
    bench-restore` from the workstation) refuses this one, the VM never deallocated; the executor's
    and the CLI's path alike (both reach restore_from_backup)."""
    from glorfindel.providers.azure.restore import RestoreJobRunning
    f, c, vm = _vault_world(monkeypatch)
    now = datetime.now(timezone.utc)
    f.add_point(vm, "p-1", now - timedelta(hours=3))
    f.restore(vm, "p-1", now - timedelta(minutes=5), None)                    # InProgress
    before = json.dumps(f.vms, default=str, sort_keys=True)
    with pytest.raises(RestoreJobRunning, match="restaure déjà web"):
        c.restore_from_backup(vm, vault="rsv-example", before_attack_time=(now - timedelta(hours=1)).isoformat(),
                              wait=False, staging_storage="stexample")
    assert json.dumps(f.vms, default=str, sort_keys=True) == before          # nothing touched


def test_only_a_running_restore_of_this_vm_counts_and_unreadable_jobs_refuse(monkeypatch):
    from glorfindel.providers.azure.restore import RestoreJobRunning
    f, c, vm = _vault_world(monkeypatch)
    now = datetime.now(timezone.utc)
    f.add_point(vm, "p-1", now - timedelta(hours=3))
    f.restore(vm, "p-1", now - timedelta(hours=2), now - timedelta(hours=1))   # finished
    assert c._restore_jobs_running(f.backup, "rsv-example", "rg-app", "rg-app", "web") == []
    f.restore(vm, "p-1", now - timedelta(minutes=1), None)
    assert c._restore_jobs_running(f.backup, "rsv-example", "rg-app", "rg-other", "web") == []   # another VM's
    assert c._restore_jobs_running(f.backup, "rsv-example", "rg-app", "rg-app", "web") != []

    class Broken:
        class backup_jobs:
            @staticmethod
            def list(*a):
                raise RuntimeError("403")
    with pytest.raises(RestoreJobRunning, match="ne se lisent pas"):
        c.refuse_if_restore_running(Broken(), "rsv-example", "rg-app", "rg-app", "web")


def test_the_executor_says_the_vaults_running_restore(world, second_factor):
    """M7274: refused (vault_job_running), the claim given back, the job never recorded."""
    from glorfindel.providers.azure.restore import RestoreJobRunning
    world["conn"].fail = RestoreJobRunning(f"le coffre restaure déjà vm-example-01 (/subscriptions/{SUB})")
    doc = _ask(world, _card())
    world["ex"].poll()
    r = _receipt(world, doc)
    assert (r["state"], r["code"]) == ("refused", "vault_job_running") and SUB not in r["reason"]
    assert not jobs.restore_in_progress(VM)


# ── The principal in Imladris's Terraform (Jonathan, 24/11) ───────────────────────────────

def test_the_restore_principal_is_declared_off_by_default_with_a_certificate_never_a_secret():
    """The contract terraform test plans (infra/glorfindel-host/tests/restore_executor.tftest.hcl), read
    in the files: off by default, no password, Restore on the groups only, its id among restore_principals."""
    from pathlib import Path
    host = Path(__file__).resolve().parents[2] / "infra" / "glorfindel-host"
    tf = (host / "restore_executor.tf").read_text(encoding="utf-8")
    block = (host / "variables.tf").read_text(encoding="utf-8").split('variable "restore_executor_enabled"', 1)[1]
    assert "default     = false" in block.split("\n}\n", 1)[0]
    assert 'resource "azuread_application_password"' not in tf
    assert tf.count('role_definition_name = "') == 1 and 'role_definition_name = "Eregion Glorfindel Restore"' in tf
    assert "executor = azuread_service_principal.restore_executor[0].object_id" in tf
    assert (host / "main.tf").read_text(encoding="utf-8").count("local.restore_principals_all") == 3
