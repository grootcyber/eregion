"""The hold read once, in the test's world (RSM2a, #1033; tests/unit/invariant_hold.py): what the machine's
oracles now rest on — L1 of a block by the content of its rules (E1), L1 of an isolation after every pass
(E5, Q4), a subnet's NSG taken off it (E7) — measured case by case, each oracle both ways, and against a
product made to lie or to keep silent: the hold is never read in the code's verification (A0)."""
from __future__ import annotations

import pytest

from .fake_azure import ATTACKER, key, subnet_id
from .invariant_hold import GONE, INTACT, UNKNOWN, block_nics, block_rules, isolation_hold
from .test_invariant_regressions import _NSG, WEB1, Script, _net, _nic
from .test_invariants import IsolationMachine, invariant_env

_WEB_NSG = _NSG.format(rg="rg-app1", name="nsg-web-nic")
_SUBNET_NSG = _NSG.format(rg="rg-net", name="nsg-subnet")
_APP = key(subnet_id("rg-net", "vnet-hub", "app"))
_PAIR = "glorfindel-block-" + ATTACKER.replace(".", "-")


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


def _own(m, vm=WEB1, prefix="glorfindel-block-") -> dict:
    """The VM's own rules of `prefix` on web's NSG, by direction."""
    rules = m.fake.nsgs[key(_WEB_NSG)]["rules"]
    return {("out" if n.endswith("-out") else "in"): n for n in rules if n.startswith(prefix)}


def _iso_cards(m, vm=WEB1) -> list[dict]:
    from glorfindel import escalations
    return [e for e in escalations.pending() if key(e.get("resource_id") or "") == key(vm)
            and e.get("action") == "isolate_vm" and (e.get("signal_id") or "").startswith("reassert-")]


def test_a_block_intact_then_turned_reads_gone(machine):
    """A block on web's own NSG reads intact; its deny turned into an allow reads gone (Q2) — the other way,
    still a deny of every way for web's address, intact; the NIC is no longer held. The block has not
    vanished for L1: one of its rules still holds."""
    m = machine(_net(web_nic={"own": "dedicated"}))
    m.block(data=Script(WEB1, WEB1, None, None))
    own = _own(m)
    assert set(block_rules(m, WEB1).values()) == {INTACT} and block_nics(m, WEB1) == {"web-nic": INTACT}
    m._tamper_with_our_rule(data=Script("access", (key(_WEB_NSG), own["in"])))
    states = block_rules(m, WEB1)
    assert states[(key(_WEB_NSG), own["in"])] == GONE, "Q2: a deny turned into an allow is gone"
    assert states[(key(_WEB_NSG), own["out"])] == INTACT
    assert block_nics(m, WEB1) == {"web-nic": GONE}
    assert not m._block_vanished(WEB1)
    m._tamper_with_our_rule(data=Script("access", (key(_WEB_NSG), own["out"])))
    assert m._block_vanished(WEB1), "E1: both denies turned, the block has vanished — by the names, never"


@pytest.mark.parametrize("how", ["port", "protocol", "retarget"])
def test_a_block_deny_narrowed_or_retargeted_reads_gone(machine, how):
    """Narrowed to a port, turned to another protocol, aimed at another address: no longer a deny of every
    way for the NIC's address — gone, as the code reads it (`altered`)."""
    m = machine(_net(web_nic={"own": "dedicated"}))
    m.block(data=Script(WEB1, WEB1, None, None))
    own = _own(m)
    m._tamper_with_our_rule(data=Script(how, (key(_WEB_NSG), own["in"])))
    assert block_rules(m, WEB1)[(key(_WEB_NSG), own["in"])] == GONE


def test_a_block_left_on_a_former_address_reads_gone_and_is_said(machine):
    """web's address changed: its block's two denies still name the former one — present by their names,
    gone by their content (L26: the new address is open). The block has vanished for L1, and the pass says
    so: the product reads the NIC's address as it is now."""
    m = machine(_net(web_nic={"own": "dedicated"}))
    m.block(data=Script(WEB1, WEB1, None, None))
    m._customer_changes_ip(Script(_nic("rg-app1", "web-nic"), 0, 20))
    assert set(block_rules(m, WEB1).values()) == {GONE}, block_rules(m, WEB1)
    assert m._block_vanished(WEB1)
    assert m._attacker_flows(WEB1, None), "the world: the new address reaches the attacker"
    m.reassert(data=Script("human_only", None))                 # L1 judges it: said
    from glorfindel import escalations
    assert any(e.get("action") == "block_suspicious_ip" and "disparu" in (e.get("reason") or "")
               for e in escalations.pending())


def test_the_hold_is_read_in_the_world_never_in_the_verification(machine, monkeypatch):
    """A0: the code's verifications made to lie — a block and an isolation always « verified », or always
    missing — the hold reads what the world holds: its rules deleted, gone; untouched, intact."""
    from glorfindel.actions import AzureConnector
    m = machine(_net(web_nic={"own": "dedicated"}))
    m.isolate(data=Script(WEB1, WEB1, None))
    m.block(data=Script(WEB1, WEB1, None, None))
    for lie in ({"verified": True, "method": "nsg_check"},
                {"verified": False, "method": "nsg_check", "missing_rules": ["x"], "uncovered_nics": ["web-nic"]}):
        monkeypatch.setattr(AzureConnector, "verify_block_ip", lambda self, *a, **k: dict(lie))
        monkeypatch.setattr(AzureConnector, "verify_isolation", lambda self, *a, **k: dict(lie))
        assert set(block_rules(m, WEB1).values()) == {INTACT}
        assert isolation_hold(m, WEB1)[0] == {"web-nic": INTACT}
    rules = m.fake.nsgs[key(_WEB_NSG)]["rules"]
    for n in [n for n in rules if n.startswith("glorfindel-")]:
        del rules[n]
    assert set(block_rules(m, WEB1).values()) == {GONE}
    assert isolation_hold(m, WEB1)[0] == {"web-nic": GONE}


def test_an_unread_nsg_reads_unknown(machine):
    """An NSG the identity can't read (its role removed): neither intact nor gone (A0) — the block not
    vanished, its NIC unknown."""
    m = machine(_net(web_nic={"own": "dedicated"}))
    m.block(data=Script(WEB1, WEB1, None, None))
    rules = m.fake.nsgs[key(_WEB_NSG)]["rules"]
    for n in [n for n in rules if n.startswith("glorfindel-")]:
        del rules[n]
    m.fake.unreadable.add(key(_WEB_NSG))
    try:
        assert set(block_rules(m, WEB1).values()) == {UNKNOWN}
        assert block_nics(m, WEB1) == {"web-nic": UNKNOWN} and not m._block_vanished(WEB1)
        assert isolation_hold(m, WEB1)[0] == {"web-nic": UNKNOWN}
    finally:
        m.fake.unreadable.discard(key(_WEB_NSG))         # given back: the teardown releases web (I7)


def test_an_isolation_gone_is_said_after_a_pass(machine):
    """E5 (Q4): web isolated by rules, a `terraform apply` takes them off — drawn alone, no composite rule.
    The isolation reads gone; after the pass, a card of the reassertion's says it."""
    m = machine(_net(web_nic={"own": "dedicated"}))
    m.isolate(data=Script(WEB1, WEB1, None))
    assert isolation_hold(m, WEB1)[0] == {"web-nic": INTACT}
    m.terraform_apply(data=Script(key(_WEB_NSG)))
    assert isolation_hold(m, WEB1)[0] == {"web-nic": GONE}
    m.reassert(data=Script("human_only", None))
    assert _iso_cards(m), "the product says the isolation gone"


def test_an_isolation_gone_and_unsaid_fails_l1(machine, monkeypatch):
    """The other side: the product made silent on isolations, the oracle demands the card after an ordinary
    pass — L1 of an isolation no longer waits for a composite rule."""
    from glorfindel import reassert
    m = machine(_net(web_nic={"own": "dedicated"}))
    m.isolate(data=Script(WEB1, WEB1, None))
    m.terraform_apply(data=Script(key(_WEB_NSG)))
    monkeypatch.setattr(reassert, "_reassert_isolation", lambda *a, **k: None)
    with pytest.raises(AssertionError, match="L1: the isolation of .* is gone from web-nic"):
        m.reassert(data=Script("human_only", None))


def test_an_isolation_turned_is_gone_and_one_moved_holds(machine):
    """An isolation deny turned into an allow: gone; one moved to another priority, still a deny of
    everything: intact (its bytes changed, not its content)."""
    m = machine(_net(web_nic={"own": "dedicated"}))
    m.isolate(data=Script(WEB1, WEB1, None))
    own = _own(m, prefix="glorfindel-iso-")
    m._tamper_with_our_rule(data=Script("priority", (key(_WEB_NSG), own["in"])))
    assert isolation_hold(m, WEB1)[0] == {"web-nic": INTACT}
    m._tamper_with_our_rule(data=Script("access", (key(_WEB_NSG), own["out"])))
    assert isolation_hold(m, WEB1)[0] == {"web-nic": GONE}


@pytest.mark.parametrize("how", ["off", "replaced"])
def test_a_subnet_that_lost_its_nsg_leaves_the_perimeter_gone(machine, how):
    """E7: web blocked on its subnet (a perimeter pair on nsg-subnet); the customer takes the NSG off the
    subnet, or puts another of its own there — its rules, never ours. The pair, present, governs nothing:
    gone; the design follows the customer (I2). The pass says it (the measure M5: « ne couvre pas »). The
    NSG put back: the pair holds again."""
    m = machine(_net(subnet_nsg=[]))
    m.block_perimeter(data=Script(WEB1, WEB1, None, False))
    pair = {(k, n) for (k, n) in block_rules(m, WEB1) if n in (_PAIR, f"{_PAIR}-out")}
    assert pair and all(block_rules(m, WEB1)[k] == INTACT for k in pair)
    m.customer_changes_subnet_nsg(data=Script(_APP, how))
    now = m.fake.subnets[_APP]["nsg"]
    assert key(now or "") != key(_SUBNET_NSG) and key(m.design["subnets"][_APP]["nsg"] or "") == key(now or "")
    if how == "replaced":
        assert not [n for n in m.fake.nsgs[key(now)]["rules"] if n.startswith("glorfindel-")], "never ours"
    assert all(block_rules(m, WEB1)[k] == GONE for k in pair), block_rules(m, WEB1)
    assert m._block_vanished(WEB1)
    m.customer_configuration_untouched()
    m.reassert(data=Script("human_only", None))
    from glorfindel import escalations
    assert any(e.get("action") == "block_suspicious_ip" and key(e.get("resource_id") or "") == key(WEB1)
               for e in escalations.pending())
    m.customer_changes_subnet_nsg(data=Script(_APP, "back"))
    assert key(m.fake.subnets[_APP]["nsg"]) == key(_SUBNET_NSG)
    assert all(block_rules(m, WEB1)[k] == INTACT for k in pair)


def test_a_rule_nothing_records_on_a_subnets_nsg_taken_off_is_out_of_reach(machine):
    """E7, the oracle's limit (the 2 000 examples of RSM2a, 22/11): web's block cut off after its first write —
    its rule on nsg-subnet, no record written —, then the NSG taken off the subnet. Nothing ties the rule to web
    any more: the teardown's unblock, without a record, can't read it (`_loose`, as `_untied`, I8F). With a
    record, the release reads its placements, and takes them off."""
    m = machine(_net(subnet_nsg=[]))
    m.block(data=Script(WEB1, WEB1, (1, "after-crash"), None))
    assert [n for n in m.fake.nsgs[key(_SUBNET_NSG)]["rules"] if n.startswith("glorfindel-block-")], "the world"
    assert not m._loose(WEB1), "the NSG still governs web: nothing out of reach"
    m.customer_changes_subnet_nsg(data=Script(_APP, "off"))
    assert {g for g, _ in m._loose(WEB1)} == {key(_SUBNET_NSG)}


@pytest.mark.parametrize("lost", ["before the block", "after the block"])
def test_a_rule_its_entry_still_names_stays_in_reach(machine, lost):
    """`_loose` only exempts what nothing records (the review of RSM2a): web's state lost — before its block,
    or after it —, the block written whole, its entry naming nsg-subnet, then the NSG taken off the subnet.
    The entry still names it: the unblock's to take off, never out of reach."""
    m = machine(_net(subnet_nsg=[]))
    if lost == "before the block":
        m._lose_state(WEB1)
    m.block(data=Script(WEB1, WEB1, None, None))
    if lost == "after the block":
        m._lose_state(WEB1)
    m.customer_changes_subnet_nsg(data=Script(_APP, "off"))
    assert [n for n in m.fake.nsgs[key(_SUBNET_NSG)]["rules"] if n.startswith("glorfindel-block-")], "the world"
    assert not m._loose(WEB1), m._loose(WEB1)


def _bypass_card(vm, nsg: str):
    from glorfindel import escalations
    escalations.record(signal_id="reassert-bypass-block-web-0", resource_id=vm, action="review_bypass",
                       escalation_type="bypassed", confidence=1.0, severity="high", action_params={"ip": ATTACKER},
                       reason=f"Le blocage est contourné : 'allow-x' (priorité 95, inbound, ports *, {nsg}) passe avant")


@pytest.mark.parametrize("how", ["perimeter, its NSG named", "perimeter, another NSG named", "a placement",
                                 "own NSG off its NIC"])
def test_no_excuse_is_left_for_an_nsg_taken_off(machine, monkeypatch, how):
    """RSM3 (#1057, #1036): the excuse `_known_1057` gone with the defect's fix — a perimeter pair gone only for
    where it lies, on an NSG taken off its subnet, and a « contourné » card that names that NSG, is excused no
    more than the other cases (a card naming another NSG, a VM's placement on the NSG taken off, web's own NSG
    taken off its NIC: L1N's world). The product made silent on blocks, L1 demands each disappearance."""
    from glorfindel import reassert
    own = how == "own NSG off its NIC"
    m = machine(_net(subnet_nsg=[], web_nic={"own": "dedicated"} if own else {}))
    if how.startswith("perimeter"):
        m.block_perimeter(data=Script(WEB1, WEB1, None, False))
    else:
        m.block(data=Script(WEB1, WEB1, None, None))
    nic = _nic("rg-app1", "web-nic")
    if own:
        m.fake.nics[nic]["nsg"] = None
        m.detached.add(nic)
    else:
        m.customer_changes_subnet_nsg(data=Script(_APP, "off"))
    try:
        assert m._block_vanished(WEB1), "the world: its rules, intact, govern nothing"
        _bypass_card(WEB1, "rg-app1/nsg-web-nic" if how in ("perimeter, another NSG named", "own NSG off its NIC")
                     else "rg-net/nsg-subnet")
        assert not hasattr(m, "_known_1057"), "the excuse goes with the fix"
        monkeypatch.setattr(reassert, "_reassert_block", lambda *a, **k: None)
        with pytest.raises(AssertionError, match="L1: the block on .*web vanished"):
            m.reassert(data=Script("human_only", None))
    finally:
        if own:
            m.fake.nics[nic]["nsg"] = m.fake.nics[nic]["design_nsg"]
            m.detached.discard(nic)


_BEHIND = ["the quarantine holds", "the quarantine emptied", "the quarantine opened to the attacker"]


def _blocked_then_quarantined(machine, how: str):
    """web blocked on its own NSG, then isolated into our quarantine: the block's denies lie on an NSG off
    the NIC. The quarantine then left whole, emptied, or — the forensic access the operator gave naming the
    attacker — whole, and still letting the attacker in."""
    net = _net(quarantine=True, web_nic={"own": "dedicated"})
    net["config"]["forensic"] = [ATTACKER] if how == _BEHIND[2] else []
    m = machine(net)
    m.block(data=Script(WEB1, WEB1, None, None))
    m.isolate(data=Script(WEB1, WEB1, None))
    q = m.fake.nics[_nic("rg-app1", "web-nic")]["nsg"]
    assert q and "quarantine" in q, "the world: web in our quarantine"
    if how == _BEHIND[1]:
        m._strip_quarantine_nsg(Script(key(q)))
    assert m._quarantine_intact(key(q)) is (how != _BEHIND[1])
    return m, _own(m)


@pytest.mark.parametrize("how", _BEHIND)
def test_behind_a_quarantine_the_ack_reads_the_block_as_the_code_does(machine, how):
    """RSM3's night (25/11): the quarantine's leniency — a NIC in quarantine has its block's rules read
    wherever they lie — holds at the acknowledgement only while the quarantine cuts the attacker off, as the
    code reads them behind it (`_quarantine_blocks` « blocks »); emptied, or opened to the attacker by the
    forensic access, the code says them gone (« ne gouverne plus »), and so does the acknowledgement's
    reading. Outside the acknowledgement, the leniency stays whole."""
    m, own = _blocked_then_quarantined(machine, how)
    rules = [(key(_WEB_NSG), own["in"]), (key(_WEB_NSG), own["out"])]
    assert all(block_rules(m, WEB1)[r] == INTACT for r in rules), "outside the ack, read behind the quarantine"
    held = how == _BEHIND[0]
    assert all(block_rules(m, WEB1, at_ack=True)[r] == (INTACT if held else GONE) for r in rules), (
        how, block_rules(m, WEB1, at_ack=True))


@pytest.mark.parametrize("how", _BEHIND)
def test_an_acknowledged_block_behind_a_quarantine_turned_since(machine, how):
    """The acknowledgement then a deny of the block turned into an allow. Behind a quarantine that held at the
    acknowledgement, the deny was read intact: turned, it is a worse disappearance, to be said again (M7572).
    Behind one that no longer cut the attacker off, it was gone and said already: no worse (M7573, and
    M7574 for the forensic access that opens it)."""
    m, own = _blocked_then_quarantined(machine, how)
    m.acked_drift = {WEB1: m._block_rules_now(WEB1)}
    m._acked_at(WEB1)
    assert m._ack_holds(WEB1) is True
    m._tamper_with_our_rule(data=Script("access", (key(_WEB_NSG), own["in"])))
    assert m._ack_holds(WEB1) is (how != _BEHIND[0]), (how, m.acked_hold[WEB1])
