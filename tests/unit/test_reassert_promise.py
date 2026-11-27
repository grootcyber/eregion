"""RSM6 (#1263): the reassertion keeps its word — on the invariant machine's fake Azure (hermetic, no call to
Azure nor to a model; docs/design/reaffirmation.md §3.1 R3, §3.2, §3.6).

1. **A pair deferred for want of a read, nothing written** (RSM5's review): a perimeter alone, its pair gone,
   the subnet's NSG unread at the write (`perimeter_nsg_now`, a 429: `PairUnread`). Every write failed, the
   card promised the pair « une fois, à la passe suivante si la lecture le permet » — and the next pass was
   silent (`still_said`): `defer_marks` ran only where something was written. Now the pair is put back once, on
   its own NSG only, at the first pass that reads; the card's words end with their full stop.
2. **The card « réaffirmation sautée »** (`reassert-busy-…`): its count in memory, a restart left it pending;
   a VM lifted while skipped is no longer read, its card left pending. Now it closes at the first pass that reads
   the VM, a restart or not, and once the VM is lifted or unblocked — never while the VM is still skipped.
"""
from __future__ import annotations

import contextlib

import pytest

from .fake_azure import ATTACKER, key
from .test_invariant_regressions import _NSG, WEB1, WEB2, Script, _net
from .test_invariants import _CURRENT, IsolationMachine, invariant_env
from .test_reassert_gone import _cards, _flaky_nics, _merged_all_gone, _pair_on, _pass, _strip

_SUBNET = key(_NSG.format(rg="rg-net", name="nsg-subnet"))
_TIER = key(_NSG.format(rg="rg-net", name="nsg-tier"))


@pytest.fixture
def machine(monkeypatch):
    """The machine's world, built for one test (as `test_reassert_gone.py`'s), torn down after it."""
    invariant_env(monkeypatch)
    made = []

    def make(net, mode="human_only"):
        m = IsolationMachine()
        made.append(m)
        m.build(net)
        _CURRENT.mode = mode
        return m
    yield make
    for m in made:
        m.teardown()


def _alone_gone(machine):
    """web (rg-app1) blocked on its subnet alone, its pair gone, outside human_only."""
    m = machine(_net(subnet_nsg=[]), "non_disruptive")
    m.block_perimeter(data=Script(WEB1, WEB1, None, False))
    _strip(m, "nsg-subnet")
    return m


def _drift(vm: str) -> dict:
    (card,) = _cards(vm, escalation_type="verification_failed")
    return card


# ── 1. a pair deferred, nothing written ─────────────────────────────────────────────────────────────────────

@pytest.mark.parametrize("time", ["first", "second"], ids=["refused at the first time", "the first time skipped"])
def test_a_perimeter_alone_refused_unread_is_put_back_once_at_the_next_pass(machine, monkeypatch, time):
    """The case of the issue: nothing written at pass 1, its card promises the pair « à la passe suivante » — with
    a full stop before it; pass 2, reading, puts it back once, on its own NSG only, « reposé une fois »; gone again,
    said « une deuxième fois », never written again."""
    from glorfindel import reassert
    from glorfindel.actions import _load_block_entries
    m = _alone_gone(machine)
    with monkeypatch.context() as mp:
        _flaky_nics(m, mp, "subnet")
        if time == "second":
            mp.setattr(reassert, "put_back_perimeters", lambda *a, **k: {})      # its lock held at the first
        report, writes = _pass(m)
    assert not writes and not _pair_on(m, "nsg-subnet"), writes
    assert [r["outcome"] for r in report if r.get("kind") == "block"] == ["failed"], report
    entry = _load_block_entries(WEB1)[0]
    assert entry.get("pair_deferred") and not entry.get("reasserted_at"), entry    # deferred, nothing spent
    reason = _drift(WEB1)["reason"]
    assert "rien n'est posé. Sa règle de périmètre n'a pas été reposée, faute de lecture" in reason, reason
    assert "à la passe suivante si la lecture le permet" in reason, reason
    report, writes = _pass(m)                                  # the read back: the promise kept
    assert writes and {e["nsg"] for e in writes} == {_SUBNET}, writes      # on its own NSG only
    assert len(_pair_on(m, "nsg-subnet")) == 2, "pass 2: the pair put back"
    assert [r["outcome"] for r in report if r.get("kind") == "block"] == ["reapplied"], report
    assert "reposé une fois" in _drift(WEB1)["reason"], _drift(WEB1)
    entry = _load_block_entries(WEB1)[0]
    assert not entry.get("pair_deferred") and entry.get("reasserted_at"), entry
    _strip(m, "nsg-subnet")
    _, writes = _pass(m)
    assert not writes and "une deuxième fois" in _drift(WEB1)["reason"], (writes, _drift(WEB1))


@pytest.mark.parametrize("entry", ["alone", "merged"])
def test_a_deferred_pair_refused_unread_again_stays_deferred_until_the_read_passes(machine, monkeypatch, entry):
    """Jonathan's decision (27/11): refused for want of a read, the pair stays deferred — one read a pass,
    nothing written while where it lands is unknown, one card brought up to date (the same card, no new one a
    pass), still promising; the read back, it is put back once, on its own NSG — « sinon à la première qui le
    permet » holds. A merged entry's VM rules, written once at pass 1, are never written again meanwhile."""
    from glorfindel.actions import _load_block_entries
    vm = WEB1 if entry == "alone" else WEB2
    m = _alone_gone(machine) if entry == "alone" else _merged_all_gone(machine)
    passes, reads = [], []
    with monkeypatch.context() as mp:
        _flaky_nics(m, mp, "subnet")
        from glorfindel.actions import AzureConnector
        unread = AzureConnector.perimeter_nsg_now
        mp.setattr(AzureConnector, "perimeter_nsg_now", lambda self, rid: reads.append(rid) or unread(self, rid))
        for _ in range(3):
            passes.append(_pass(m)[1])
            if entry == "merged":
                _strip(m, "nsg-tier")                  # the customer's Terraform, again
    assert not any(_SUBNET in {e["nsg"] for e in w} for w in passes), passes       # nothing on an unknown
    assert sum(1 for w in passes if _TIER in {e["nsg"] for e in w}) == (entry == "merged"), passes
    assert len(reads) == 3, reads                                  # one read a pass
    card = _drift(vm)
    assert card.get("first_reason"), "brought up to date, not replaced"
    assert "sinon à la première qui le permet" in card["reason"], card
    assert _load_block_entries(vm)[0].get("pair_deferred"), "still deferred"
    _, writes = _pass(m)                                           # the read back
    assert {e["nsg"] for e in writes} == {_SUBNET} and len(_pair_on(m, "nsg-subnet")) == 2, writes
    assert not _load_block_entries(vm)[0].get("pair_deferred")
    _strip(m, "nsg-subnet")
    _, writes = _pass(m)
    assert not writes, ("put back once: said, never written again", writes)


def test_a_pair_deferred_again_writes_nothing_in_human_only(machine, monkeypatch):
    """Deferred, refused unread twice, then the VM in human_only and the read back: nothing is written."""
    from .test_invariants import _CURRENT as current
    m = _alone_gone(machine)
    with monkeypatch.context() as mp:
        _flaky_nics(m, mp, "subnet")
        _pass(m)
        _pass(m)
    current.mode = "human_only"
    _, writes = _pass(m)
    assert not writes and not _pair_on(m, "nsg-subnet"), writes


def test_a_merged_entry_unspent_put_back_in_part_says_its_rules_written_once(machine, monkeypatch):
    """The `unspent` case of a merged entry: nothing written at pass 1; at pass 2 the pair and the VM's rules
    written, the VM's said partial by the provider. Its card says « ses règles réécrites une fois » — both were
    written —, never « sa règle de périmètre reposée une fois, reportée faute de lecture »."""
    m = _merged_all_gone(machine)
    real = m.connector.block_suspicious_ip

    def refused(ip, rid, scope="vm", **k):
        if scope == "vm":
            raise RuntimeError("(TooManyRequests) nsg.write")
        return real(ip, rid, scope=scope, **k)

    def partial(ip, rid, scope="vm", **k):
        out = real(ip, rid, scope=scope, **k)
        return {"status": "partial", "error": "une carte en partie"} if scope == "vm" else out
    with monkeypatch.context() as mp:
        _flaky_nics(m, mp, "subnet")
        mp.setattr(m.connector, "block_suspicious_ip", refused)
        _pass(m)
    with monkeypatch.context() as mp:
        mp.setattr(m.connector, "block_suspicious_ip", partial)
        report, _ = _pass(m)
    assert [r["outcome"] for r in report if r.get("kind") == "block"] == ["partial"], report
    reason = _drift(WEB2)["reason"]
    assert "ses règles réécrites une fois" in reason and "reportée faute de lecture" not in reason, reason


def test_a_deferred_pair_is_never_put_back_in_human_only_nor_while_unread(machine, monkeypatch):
    """Deferred, nothing written; then the VM in human_only, the read back: nothing is written."""
    from .test_invariants import _CURRENT as current
    m = _alone_gone(machine)
    with monkeypatch.context() as mp:
        _flaky_nics(m, mp, "subnet")
        _pass(m)
    current.mode = "human_only"
    _, writes = _pass(m)
    assert not writes and not _pair_on(m, "nsg-subnet"), writes


def test_a_merged_entry_whose_writes_all_failed_puts_both_back_once(machine, monkeypatch):
    """A merged entry, its pair and its own rules gone; at pass 1 the pair refused unread and the VM's write
    refused too: nothing written, nothing spent. Pass 2 puts the pair back on its own NSG and the VM's rules on
    theirs — each once —, the VM's never left unwritten by a put-back of the pair alone; gone again, said."""
    m = _merged_all_gone(machine)
    real = m.connector.block_suspicious_ip

    def refused(ip, rid, scope="vm", **k):
        if scope == "vm":
            raise RuntimeError("(TooManyRequests) nsg.write")
        return real(ip, rid, scope=scope, **k)
    with monkeypatch.context() as mp:
        _flaky_nics(m, mp, "subnet")
        mp.setattr(m.connector, "block_suspicious_ip", refused)
        _, writes = _pass(m)
    assert not writes, writes
    assert "nsg.write. Sa règle de périmètre n'a pas été reposée" in _drift(WEB2)["reason"], _drift(WEB2)
    _, writes = _pass(m)
    assert {e["nsg"] for e in writes} == {_SUBNET, _TIER}, writes
    assert len(_pair_on(m, "nsg-subnet")) == 2
    assert "reportée faute de lecture" not in _drift(WEB2)["reason"], _drift(WEB2)
    _strip(m, "nsg-subnet", "nsg-tier")
    _, writes = _pass(m)
    assert not writes, ("spent: said, never written again", writes)


def test_the_note_ends_the_sentence_before_it():
    from glorfindel.reassert_gone import deferred_said
    said = deferred_said("… le reposer a échoué : refusé : le NSG du sous-réseau ne se lit pas (x) — rien n'est posé",
                         True)
    assert "rien n'est posé. Sa règle de périmètre" in said, said
    assert deferred_said("… a échoué : x.", True).count("..") == 0
    assert deferred_said("le reposer a échoué : x", False) == "le reposer a échoué : x.", "not deferred: its stop"
    assert deferred_said("… sinon re-bloquer.", False) == "… sinon re-bloquer."


# ── 2. the card « réaffirmation sautée » ────────────────────────────────────────────────────────────────────

def _busy_world(monkeypatch, rid: str):
    """One isolation recorded; its lock held while `busy["on"]`; the pass's own work stubbed (the cards counted)."""
    from glorfindel import actions, escalations, reassert
    from glorfindel.actions import _save_isolation_state
    monkeypatch.setattr(escalations, "_notify", lambda esc: None)
    _save_isolation_state(rid, {"resource_id": rid, "isolated_at": "2026-11-18T10:00:00+00:00", "placements": []})
    busy = {"on": True}

    @contextlib.contextmanager
    def lock(vm, timeout=None):
        if busy["on"]:
            raise TimeoutError("busy")
        yield
    monkeypatch.setattr(actions, "_vm_lock", lock)
    monkeypatch.setattr(reassert, "_reassert_isolation", lambda *a, **k: None)
    monkeypatch.setattr(reassert, "put_back_perimeters", lambda *a, **k: {})
    monkeypatch.setattr(reassert, "_whatever_the_state", lambda *a, **k: None)
    return busy


def _busy_cards() -> list[dict]:
    from glorfindel import escalations
    return [e for e in escalations.pending() if e["signal_id"].startswith("reassert-busy-")]


_RID = "/subscriptions/0000/resourceGroups/rg-a/providers/Microsoft.Compute/virtualMachines/web"


def _skip_until_said(busy):
    from glorfindel import reassert, reassert_skipped
    busy["on"] = True
    for _ in range(reassert_skipped.skips_said()):
        reassert.reassert_pass(None)
    assert len(_busy_cards()) == 1


def test_the_skip_card_closes_at_the_first_read_after_a_restart(monkeypatch):
    """Said, then the watch restarted (its count in memory, gone): still skipped, the card stays; the first pass
    that reads the VM closes it."""
    from glorfindel import reassert, reassert_skipped
    busy = _busy_world(monkeypatch, _RID)
    _skip_until_said(busy)
    monkeypatch.setattr(reassert_skipped, "_SKIPPED", {})            # a restart
    reassert.reassert_pass(None)
    assert len(_busy_cards()) == 1, "still skipped: never closed"
    monkeypatch.setattr(reassert_skipped, "_SKIPPED", {})            # a restart again
    busy["on"] = False
    reassert.reassert_pass(None)
    assert not _busy_cards(), "read again: closed"


@pytest.mark.parametrize("what", ["isolation", "block"])
def test_the_skip_card_closes_once_the_vm_is_lifted(monkeypatch, what):
    """The VM said skipped, then lifted (or unblocked) while skipped: no pass reads it any more — its card closes;
    a held VM's card beside it stays, a restart between or not."""
    from glorfindel import actions, reassert, reassert_skipped
    other = _RID.replace("/web", "/db")
    _busy_world(monkeypatch, _RID)
    actions._save_isolation_state(other, {"resource_id": other, "isolated_at": "2026-11-18T10:00:00+00:00",
                                          "placements": []})
    if what == "block":
        actions._clear_isolation_state(_RID)
        monkeypatch.setattr(reassert, "_reassert_block", lambda *a, **k: None)
        actions._save_block_state("web", ATTACKER, _RID, nsg="rg-a/nsg-web", nsg_scope="nic", rule="r",
                                  placements=[{"nsg_rg": "rg-a", "nsg_name": "nsg-web", "rule": "r"}])
    for _ in range(reassert_skipped.skips_said()):
        reassert.reassert_pass(None)
    assert len(_busy_cards()) == 2, _busy_cards()
    if what == "block":
        actions._clear_block_state(_RID, ATTACKER)
    else:
        actions._clear_isolation_state(_RID)
    reassert.reassert_pass(None)                     # db still skipped, web lifted
    (left,) = _busy_cards()
    assert "-db-" in left["signal_id"], left
    monkeypatch.setattr(reassert_skipped, "_SKIPPED", {})
    reassert.reassert_pass(None)
    assert len(_busy_cards()) == 1, "db still skipped: kept"


def test_a_lifted_vm_skipped_again_counts_from_one(monkeypatch):
    """Its run of skips over once it is no longer read: re-isolated later, skipped, its card comes at the
    `skips_said()`-th skip again — a count left from before never passes the mark in silence."""
    from glorfindel import reassert, reassert_skipped
    from glorfindel.actions import _clear_isolation_state, _save_isolation_state
    busy = _busy_world(monkeypatch, _RID)
    for _ in range(reassert_skipped.skips_said() - 1):
        reassert.reassert_pass(None)
    _clear_isolation_state(_RID)
    reassert.reassert_pass(None)
    _save_isolation_state(_RID, {"resource_id": _RID, "isolated_at": "2026-11-19T10:00:00+00:00", "placements": []})
    for n in range(1, reassert_skipped.skips_said() + 1):
        reassert.reassert_pass(None)
        assert len(_busy_cards()) == (1 if n == reassert_skipped.skips_said() else 0), n
    busy["on"] = False


def test_the_skip_card_stays_while_a_state_is_unreadable(monkeypatch):
    """The VM no longer listed because its state can't be read: what it holds is unknown (SEC4b) — never closed as
    « levée »; readable again and read, closed."""
    from glorfindel import actions, reassert
    busy = _busy_world(monkeypatch, _RID)
    _skip_until_said(busy)
    f = actions._state_file(actions._ISOLATION_STATE_DIR, _RID)
    good = f.read_text()
    f.write_text("{not json")
    reassert.reassert_pass(None)
    assert len(_busy_cards()) == 1
    f.write_text(good)
    busy["on"] = False
    reassert.reassert_pass(None)
    assert not _busy_cards()


def test_the_skip_sweep_never_raises(monkeypatch):
    """The store that raises: the pass goes on, nothing raised (as `read`)."""
    from glorfindel import escalations, reassert_skipped
    from glorfindel.reassert_cards import new_pass
    new_pass()
    monkeypatch.setattr(escalations, "all_escalations", lambda: (_ for _ in ()).throw(OSError("disk")))
    reassert_skipped.settle()
    reassert_skipped.read("web", _RID)


def test_a_lock_that_raises_an_oserror_never_closes_the_card_as_lifted(monkeypatch):
    """The relecture's probe: the VM's lock raises a PermissionError (`unrecorded`): the VM is neither read nor
    skipped, yet still recorded — its card stays, never « Levé : plus rien d'enregistré »."""
    from glorfindel import actions, reassert
    busy = _busy_world(monkeypatch, _RID)
    _skip_until_said(busy)

    @contextlib.contextmanager
    def denied(vm, timeout=None):
        raise PermissionError("lock file")
        yield
    monkeypatch.setattr(actions, "_vm_lock", denied)
    report = reassert.reassert_pass(None)
    assert any(r.get("outcome") != "skipped" for r in report), report
    (card,) = _busy_cards()
    assert actions.active_isolations(), "still recorded"


def test_a_vm_read_while_another_state_is_unreadable_has_its_card_closed_as_read(monkeypatch):
    """Another VM's state unreadable (SEC4b): the VM read again closes its card all the same, with « relit »."""
    from glorfindel import actions, escalations, reassert
    busy = _busy_world(monkeypatch, _RID)
    _skip_until_said(busy)
    (card,) = _busy_cards()
    (actions._ISOLATION_STATE_DIR / "another.json").write_text("{not json")
    assert actions.unreadable_states(), "another state unreadable"
    busy["on"] = False
    reassert.reassert_pass(None)
    assert not _busy_cards()
    (closed,) = [e for e in escalations.all_escalations() if e["id"] == card["id"]]
    assert closed["resolution"] == "La réaffirmation relit la VM de nouveau.", closed


def test_a_card_acknowledged_during_the_pass_is_never_closed_again(monkeypatch):
    """The pass's cache of its cards read before the operator acknowledged the card: `settle` reads the store
    again — the operator's word stays, never overwritten by « relit »."""
    from glorfindel import escalations, reassert_skipped
    from glorfindel.reassert_cards import _history
    busy = _busy_world(monkeypatch, _RID)
    _skip_until_said(busy)
    (card,) = _busy_cards()
    _history()                                             # the pass's cache, loaded
    escalations.resolve(card["id"], note="vu, l'opérateur")
    reassert_skipped.read("web", _RID)
    reassert_skipped.settle()
    (closed,) = [e for e in escalations.all_escalations() if e["id"] == card["id"]]
    assert closed["resolution"] == "vu, l'opérateur", closed
