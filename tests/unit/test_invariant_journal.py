"""What holds a hold, read in the test's journal (RSM2b, #1034; docs/design/reaffirmation.md §5, E3; Q3 —
Jonathan, 21/11). L1, L3 and the bypass leave alone an isolation or a block that an operation holds — a
release or an unblock under way, one cut off, one partial. The machine read that in the code's marks
(`partial`, `release_failed`, `releasing_at`, `unblock_failed`, `unblocking_at`): a defect that set one
would silence those oracles for its VM, and no oracle would see it (A0). It now notes what it saw of each
operation of the connector's — its answer, its error, its writes of the VM's state that landed — and reads
only that (`_held_by`, `_iso_held`, `_block_held`). Measured both ways: a mark a defect sets exempts
nothing; a hold the product keeps is exempt by the journal, the code's marks never read; a hold ends once
the test sees it written whole."""
from __future__ import annotations

from datetime import datetime, timezone

import pytest

from glorfindel import actions, reassert

from .fake_azure import ATTACKER, key
from .test_invariant_regressions import _ISO1_NET, _NSG, DB, WEB1, Script, _net, _nic
from .test_invariants import IsolationMachine, invariant_env

_WEB_NSG = key(_NSG.format(rg="rg-app1", name="nsg-web-nic"))


@pytest.fixture
def machine(monkeypatch):
    invariant_env(monkeypatch)
    made = []

    def make(net):
        m = IsolationMachine()
        made.append(m)
        m.build(net)
        return m
    yield make
    for m in made:
        m.teardown()


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


@pytest.mark.parametrize("mark", ["partial", "releasing_at", "release_failed"])
def test_a_mark_a_defect_sets_on_a_whole_isolation_exempts_nothing(machine, mark):
    """web isolated whole; a defect marks its state as held by an operation — none ran. The code then leaves
    the isolation to the operator, in silence, once a `terraform apply` takes its rules off. The test saw no
    operation cut off nor partial: L1 demands the card (M7050 for `partial`, M7051 for `releasing_at`)."""
    m = machine(_net(web_nic={"own": "dedicated"}))
    m.isolate(data=Script(WEB1, WEB1, None))
    assert key(WEB1) not in m.iso_held and WEB1 not in m.releasing, "the journal: written whole"
    actions._save_isolation_state(WEB1, {**m._state(WEB1), mark: True if mark == "partial" else _now()})
    m.terraform_apply(data=Script(_WEB_NSG))
    with pytest.raises(AssertionError, match="L1: the isolation of .*web is gone from web-nic"):
        m.reassert(data=Script("human_only", None))


@pytest.mark.parametrize("mark", ["partial", "unblock_failed", "unblocking_at"])
def test_a_mark_a_defect_sets_on_a_whole_block_exempts_nothing(machine, mark):
    """The same for a block: web blocked whole, its entry marked by a defect, its rules taken off — the code
    holds it, nothing said; L1 demands it (M7050 for `partial`)."""
    m = machine(_net(web_nic={"own": "dedicated"}))
    m.block(data=Script(WEB1, WEB1, None, 22))
    assert key(WEB1) not in m.block_held and WEB1 not in m.unblocking, "the journal: written whole"
    actions._update_block_entry(WEB1, ATTACKER, **{mark: True if mark == "partial" else _now()})
    m.terraform_apply(data=Script(_WEB_NSG))
    with pytest.raises(AssertionError, match="L1: the block on .*web vanished"):
        m.reassert(data=Script("human_only", None))


def test_a_partial_isolation_on_its_own_is_held_by_the_journal(machine):
    """ISO1's world: Db--01's db-nic-0 isolated, db-nic-1 refused (no NSG, the quarantine off) — no fault
    played, the isolation partial in its answer (`PartialActionError`), its state written. The code leaves
    the VM to the operator; the test's journal holds it too, never its `partial` mark: L1 waits (M7053: a
    hold begun by a fault alone made L1 demand what the product rightly leaves)."""
    m = machine(_net(**_ISO1_NET))
    m.isolate(data=Script(DB, DB, None))
    assert not m.fault_played and key(DB) in m.iso_held, (m.fault_played, m.iso_held)
    m.terraform_apply(data=Script(key(m.fake.nics[_nic("rg-app1", "db-nic-0")]["nsg"])))
    m.reassert(data=Script("human_only", None))


def test_a_release_cut_off_after_its_intent_is_held_by_the_journal(machine):
    """web's release crashed right after it wrote its intent, before any write to Azure: I9's journal lets it
    go (nothing to undo), the code holds the isolation (its intent). The test saw a write of web's state land
    in an operation cut off: it holds it too, and L1 waits."""
    m = machine(_net(web_nic={"own": "dedicated"}))
    m.isolate(data=Script(WEB1, WEB1, None))
    m.release(data=Script(WEB1, WEB1, (1, "after-crash")))
    assert WEB1 not in m.releasing and key(WEB1) in m.iso_held, (m.releasing, m.iso_held)
    m.terraform_apply(data=Script(_WEB_NSG))
    m.reassert(data=Script("human_only", None))


@pytest.mark.parametrize("what", ["isolation", "block"])
def test_a_hold_ends_once_the_test_sees_it_written_whole(machine, monkeypatch, what):
    """The journal's end (M7052): web's release cut off (its unblock failed, for a block), then web isolated
    (blocked) again, whole — the hold is over. Its rules taken off and the product made silent, L1 demands
    the card: a journal never finished held the VM for ever, L1 silent on it."""
    m = machine(_net(web_nic={"own": "dedicated"}))
    held = m.iso_held if what == "isolation" else m.block_held
    if what == "isolation":
        m.isolate(data=Script(WEB1, WEB1, None))
        m.release(data=Script(WEB1, WEB1, (1, "after-crash")))
        assert key(WEB1) in held, "the journal: a release cut off holds the isolation"
        m.isolate(data=Script(WEB1, WEB1, None))
    else:
        m.block(data=Script(WEB1, WEB1, None, 22))
        m.unblock(data=Script(WEB1, WEB1, (3, "before-429")))
        assert key(WEB1) in held, "the journal: an unblock partial holds the block"
        m.block(data=Script(WEB1, WEB1, None, 22))
    assert key(WEB1) not in held, "written whole: the hold is over"
    m.terraform_apply(data=Script(_WEB_NSG))
    monkeypatch.setattr(reassert, "_reassert_isolation", lambda *a, **k: None)
    monkeypatch.setattr(reassert, "_reassert_block", lambda *a, **k: None)
    with pytest.raises(AssertionError, match="L1: the (isolation|block) "):
        m.reassert(data=Script("human_only", None))


def test_a_lost_state_ends_its_hold(machine):
    """The test destroyed web's state: whatever held it went with it — what holds web is what is written
    next, judged when it is."""
    m = machine(_net(web_nic={"own": "dedicated"}))
    m.isolate(data=Script(WEB1, WEB1, None))
    m.release(data=Script(WEB1, WEB1, (1, "after-crash")))
    assert key(WEB1) in m.iso_held
    m._lose_state(WEB1)
    assert key(WEB1) not in m.iso_held


def test_a_perimeter_block_partial_by_its_third_argument_ends_the_hold(machine, monkeypatch):
    """A perimeter block called as queue_watch and gestures call it, its scope third (`"subnet"`), answering
    `blocked_partial` (db-nic-1 on the data subnet, off the perimeter): written whole, the code's marks of the
    unblock it supersedes gone — the hold is over too. The perimeter pair then taken off and the product made
    silent, L1 demands it (M8127: the scope read by its name alone left the hold standing)."""
    m = machine(_net(subnet_nsg=[], data_subnet=[], db_nic_0={"own": "dedicated"}, db_nic_1={"own": "dedicated"}))
    m.block(data=Script(DB, DB, None, 22))
    m.unblock(data=Script(DB, DB, (3, "before-429")))
    assert key(DB) in m.block_held, "the journal: an unblock partial holds the block"
    m.unblocking.discard(DB)                        # the test's other journal: not the one measured here
    out = m.connector.block_suspicious_ip(ATTACKER, DB, "subnet")
    assert out["status"] == "blocked_partial", out
    assert key(DB) not in m.block_held, "a perimeter block written whole ends the hold"
    m.terraform_apply(data=Script(key(_NSG.format(rg="rg-net", name="nsg-subnet"))))
    monkeypatch.setattr(reassert, "_reassert_block", lambda *a, **k: None)
    with pytest.raises(AssertionError, match="L1: the block on .*Db--01 vanished"):
        m.reassert(data=Script("human_only", None))
