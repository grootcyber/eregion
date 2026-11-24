"""RSM3 (#1036, #1057): what the reassertion says of what is no longer there — a VM deleted (Q6), a perimeter
pair on an NSG taken off its subnet (E7) —, case by case, on the invariant machine's fake Azure (hermetic, no
call to Azure): its card, its words, and nothing written (docs/design/reaffirmation.md §3.5, §3.6, E7, E8)."""
from __future__ import annotations

import pytest

from .fake_azure import ATTACKER, key, subnet_id
from .test_invariant_regressions import _NSG, DB, WEB1, WEB2, Script, _net
from .test_invariants import _CURRENT, IsolationMachine, invariant_env

_APP = key(subnet_id("rg-net", "vnet-hub", "app"))
_SUBNET_NSG = _NSG.format(rg="rg-net", name="nsg-subnet")
_WRITES = ("rule.write", "rule.delete", "nic.write", "nsg.write", "nsg.tags")


@pytest.fixture
def machine(monkeypatch):
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


def _pass(m) -> tuple[list[dict], list[dict]]:
    """One pass of the reassertion: (its report, what it wrote on the fake Azure)."""
    from glorfindel import reassert
    at = len(m.fake.journal)
    report = reassert.reassert_pass(m.connector, None)
    return report, [e for e in m.fake.journal[at:] if e.get("op") in _WRITES]


def _cards(vm: str, **match) -> list[dict]:
    from glorfindel import escalations
    return [e for e in escalations.pending() if key(e.get("resource_id") or "") == key(vm)
            and all(e.get(k) == v for k, v in match.items())]


# ── a VM deleted (Q6) ───────────────────────────────────────────────────────────────────────────────────────

@pytest.mark.parametrize("mode", ["human_only", "non_disruptive"])
@pytest.mark.parametrize("quarantine", [False, True], ids=["by rules", "in quarantine"])
def test_an_isolated_vm_deleted_has_its_own_card_closed_at_the_release(machine, mode, quarantine):
    """Its own card, « n'existe plus », with the release command — never « non vérifiée » nor « le reposer a
    échoué : (ResourceNotFound) » —, said once, nothing written; closed once the release lifts it (I7S)."""
    m = machine(_net(quarantine=quarantine, web_nic={"own": "dedicated"}), mode)
    m.isolate(data=Script(WEB1, WEB1, None))
    m._delete_vm(WEB1)
    report, writes = _pass(m)
    (card,) = _cards(WEB1)
    assert card["action"] == "review_gone_vm" and card["escalation_type"] == "vm_gone", card
    assert "web n'existe plus sur Azure" in card["reason"] and "glorfindel release rg-app1/web --yes" in card["reason"]
    assert "ResourceNotFound" not in card["reason"] and not _cards(WEB1, action="review_unverified")
    assert [r["outcome"] for r in report if r.get("vm") == "web"] == ["escalated"], report
    assert not writes, writes
    _, writes = _pass(m)
    assert len(_cards(WEB1)) == 1 and not writes, "said once"
    from glorfindel import escalations
    escalations.resolve(card["id"])                       # acknowledged: not said again
    _pass(m)
    assert not _cards(WEB1)
    assert m.connector.release_isolation(WEB1).get("status") in ("released", "not_isolated"), "the lift of a VM gone"


@pytest.mark.parametrize("rules", ["in place", "gone"])
@pytest.mark.parametrize("mode", ["human_only", "non_disruptive"])
def test_a_blocked_vm_deleted_has_its_own_card_and_nothing_is_written(machine, monkeypatch, rules, mode):
    """A block of a VM deleted: its rules in place, « non vérifiée » was said; gone, the pass tried to put them
    back (« le reposer a échoué : (ResourceNotFound) »). Its own card, with the unblock command, no write — no
    put-back even tried —; closed at the unblock."""
    m = machine(_net(web_nic={"own": "dedicated"}), mode)
    m.block(data=Script(WEB1, WEB1, None, 22))
    if rules == "gone":
        nsg = key(_NSG.format(rg="rg-app1", name="nsg-web-nic"))
        for n in [n for n in m.fake.nsgs[nsg]["rules"] if n.startswith("glorfindel-block-")]:
            m.fake.nsgs[nsg]["rules"].pop(n)
    m._delete_vm(WEB1)
    tried = []
    real = m.connector.block_suspicious_ip
    monkeypatch.setattr(m.connector, "block_suspicious_ip", lambda *a, **k: tried.append(a) or real(*a, **k))
    _, writes = _pass(m)
    (card,) = _cards(WEB1)
    assert card["action"] == "review_gone_vm" and card["action_params"] == {"ip": ATTACKER}, card
    assert f"glorfindel unblock {ATTACKER} rg-app1/web --yes" in card["reason"], card
    assert "de le blocage" not in card["reason"] and "a échoué" not in card["reason"]
    assert not tried and not writes, (tried, writes)
    m.connector.unblock_ip(ATTACKER, WEB1)
    _pass(m)
    assert not _cards(WEB1), "closed at the unblock"


def test_a_vm_whose_read_fails_is_never_read_gone(machine, monkeypatch):
    """A VM read refused (a 429), not a 404: never gone on a guess (A0) — « non vérifiée », as before."""
    m = machine(_net(web_nic={"own": "dedicated"}))
    m.block(data=Script(WEB1, WEB1, None, 22))
    with monkeypatch.context() as mp:                    # the teardown's release reads the VM again
        mp.setattr(m.connector, "verify_block_ip", lambda *a: {"verified": None, "error": "illisible"})
        mp.setattr(m.connector._compute.virtual_machines, "get",
                   lambda *a: (_ for _ in ()).throw(RuntimeError("(TooManyRequests) vm.get")))
        assert m.connector.vm_gone(WEB1) is None
        _pass(m)
    assert [e["action"] for e in _cards(WEB1)] == ["review_unverified"]
    assert "La vérification du blocage de" in _cards(WEB1)[0]["reason"], "« du blocage », never « de le »"


def test_the_unverified_card_says_du_blocage():
    from glorfindel.reassert_cards import _unverified_reason
    assert _unverified_reason(f"le blocage de {ATTACKER} sur web", "x", "x").startswith(
        f"La vérification du blocage de {ATTACKER} sur web échoue (x)")
    assert _unverified_reason("l'isolation de web", "x", "x").startswith("La vérification de l'isolation de web")


# ── a perimeter pair on an NSG taken off its subnet (E7, #1057, night n° 50) ────────────────────────────────

def _off_card(vm: str) -> list[dict]:
    return _cards(vm, escalation_type="perimeter_off")


@pytest.mark.parametrize("allow", [False, True], ids=["alone", "an allow there"])
@pytest.mark.parametrize("how", ["off", "replaced"])
@pytest.mark.parametrize("mode", ["human_only", "non_disruptive"])
def test_a_perimeter_alone_on_an_nsg_taken_off_is_said_gone_never_bypassed_nor_another_subnet(
        machine, allow, how, mode):
    """A perimeter block alone, its subnet's NSG taken off (or another put in its place), an allow added there
    or not: one card of the block that names the NSG — never « contourné » (#1057), never « autre subnet » (M5,
    #1036) —, nothing written, the subnet's new NSG left as it is; said once."""
    m = machine(_net(subnet_nsg=[]), mode)
    m.block_perimeter(data=Script(WEB1, WEB1, None, False))
    m.customer_changes_subnet_nsg(data=Script(_APP, how))
    if allow:
        m._tamper_with_our_rule(Script("rogue", key(_SUBNET_NSG)))
    check = m.connector.verify_block_ip(ATTACKER, WEB1)
    assert check["verified"] is False and check["perimeter_off"] == "rg-net/nsg-subnet", check
    assert "shadowed_by" not in check and "uncovered_nics" not in check and "missing_rules" not in check, check
    _, writes = _pass(m)
    (card,) = _cards(WEB1)
    assert card["action"] == "block_suspicious_ip" and card["escalation_type"] == "perimeter_off", card
    reason = card["reason"]
    assert "rg-net/nsg-subnet" in reason and "a disparu de son sous-réseau" in reason and "web comprise" in reason
    assert "autre subnet" not in reason and "contourné" not in reason and "ne couvre pas" not in reason
    assert f"glorfindel block {ATTACKER} rg-app1/web --scope subnet --yes" in reason
    assert not writes, writes
    _, writes = _pass(m)
    assert len(_cards(WEB1)) == 1 and not writes, "said once, nothing written"


@pytest.mark.parametrize("mode", ["human_only", "non_disruptive"])
def test_a_merged_perimeter_on_an_nsg_taken_off_is_said_and_closes_when_it_is_back(machine, mode):
    """Night n° 50: web (rg-app2) blocked on its subnet and for itself, the subnet's NSG taken off. The VM held by
    its own placement (`True`), its pair said gone on a card of its own — the VM's rules read apart —, nothing
    written. The NSG put back: the card closes, the mark goes; taken off again, said again."""
    from glorfindel import actions
    m = machine(_net(subnet_nsg=[], web_nic={"own": "tier"}), mode)
    m.block_perimeter(data=Script(WEB2, WEB2, None, False))
    m.block(data=Script(WEB2, WEB2, None, 22))
    m.customer_changes_subnet_nsg(data=Script(_APP, "off"))
    _, writes = _pass(m)
    (card,) = _off_card(WEB2)
    assert "propres règles de blocage, lues à part" in card["reason"], card
    assert not writes and len(_cards(WEB2)) == 1
    assert actions._load_block_entries(WEB2)[0]["perimeter_off_said"] == "rg-net/nsg-subnet"
    m.customer_changes_subnet_nsg(data=Script(_APP, "back"))
    _pass(m)
    assert not _off_card(WEB2) and not actions._load_block_entries(WEB2)[0].get("perimeter_off_said")
    m.customer_changes_subnet_nsg(data=Script(_APP, "off"))
    _pass(m)
    assert len(_off_card(WEB2)) == 1, "a new episode, said again"


def test_a_merged_entry_its_rules_gone_and_its_pair_off_puts_back_its_own_rules_only(machine):
    """The VM's own rules gone too, outside human_only: they are put back — the pair never, neither on the NSG
    taken off nor on the one the subnet carries now (a « replaced »). Two cards: the put-back's, the pair's."""
    m = machine(_net(subnet_nsg=[], web_nic={"own": "tier"}), "non_disruptive")
    m.block_perimeter(data=Script(WEB2, WEB2, None, False))
    m.block(data=Script(WEB2, WEB2, None, 22))
    m.customer_changes_subnet_nsg(data=Script(_APP, "replaced"))
    tier = key(_NSG.format(rg="rg-net", name="nsg-tier"))
    for n in [n for n in m.fake.nsgs[tier]["rules"] if n.startswith("glorfindel-block-")]:
        m.fake.nsgs[tier]["rules"].pop(n)
    report, writes = _pass(m)
    assert writes and {e["nsg"] for e in writes} == {tier}, writes
    assert [r["outcome"] for r in report if r.get("kind") == "block"].count("reapplied") == 1, report
    assert len(_off_card(WEB2)) == 1 and len(_cards(WEB2, escalation_type="verification_failed")) == 1


def test_a_bypass_said_before_the_nsg_is_taken_off_closes(machine):
    """A perimeter alone said « contourné » while its NSG governed the subnet; the NSG taken off: the bypass card
    closes (« contournée » supposes the hold intact), the pair's card says what is."""
    m = machine(_net(subnet_nsg=[]))
    m.block_perimeter(data=Script(WEB1, WEB1, None, False))
    m._tamper_with_our_rule(Script("rogue", key(_SUBNET_NSG)))
    _pass(m)
    assert [e["action"] for e in _cards(WEB1)] == ["review_bypass"]
    m.customer_changes_subnet_nsg(data=Script(_APP, "off"))
    _pass(m)
    assert [e["escalation_type"] for e in _cards(WEB1)] == ["perimeter_off"], [e["reason"] for e in _cards(WEB1)]


@pytest.mark.parametrize("entry", ["merged", "alone"])
def test_an_unreadable_attachment_is_never_read_gone_nor_held(machine, monkeypatch, entry):
    """The subnet of the VM's NIC unreadable (a 429), the pair's NSG governing none of its NICs as read: whether it
    still governs the subnet is not known (A0) — `None`, never `perimeter_off` (gone), never `True` (held); no
    card of the pair, nothing written."""
    m = machine(_net(subnet_nsg=[], web_nic={"own": "tier"}))
    m.block_perimeter(data=Script(WEB2, WEB2, None, False))
    if entry == "merged":
        m.block(data=Script(WEB2, WEB2, None, 22))
    real = m.connector._subnet_nsg_of

    def subnet_of(nic):
        if "web-nic" in str(getattr(nic, "id", "")).lower():
            raise RuntimeError("(TooManyRequests) subnet.get")
        return real(nic)
    with monkeypatch.context() as mp:                    # the teardown's release reads the subnet again
        mp.setattr(m.connector, "_subnet_nsg_of", subnet_of)
        check = m.connector.verify_block_ip(ATTACKER, WEB2)
        assert check["verified"] is None and "perimeter_off" not in check, check
        _, writes = _pass(m)
    assert not _off_card(WEB2) and not writes


def test_a_pair_on_its_subnet_is_never_read_off(machine):
    """The NSG on the subnet as written: the check never says the pair off — the perimeter covers it (`True`)."""
    m = machine(_net(subnet_nsg=[]))
    m.block_perimeter(data=Script(DB, DB, None, False))
    check = m.connector.verify_block_ip(ATTACKER, DB)
    assert "perimeter_off" not in check and check["verified"] is True, check
    assert not _off_card(DB)
