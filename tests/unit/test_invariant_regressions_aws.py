"""Sequences the invariant machine on AWS found failing (MC1, test_invariants_aws.py),
replayed as fixed examples on every push. A rule's draws are given in the order it makes
them — `_draw` takes the instance, then the fault.
"""
from __future__ import annotations

import pytest

from .test_invariant_regressions import Script
from .test_invariants import invariant_env
from .test_invariants_aws import _ENIS, AwsIsolationMachine


def _net(**over):
    """Every subnet on its VPC's default ACL, no rule of the customer's, the quarantine off."""
    plain = {"ingress": [], "egress": []}
    return {"web": plain, "own": {e: plain for e in _ENIS}, "default_extra": False,
            "groups": {e: [] for e in _ENIS}, "policy": {e: False for e in _ENIS},
            "acl": {"subnet-app": "default", "subnet-data": "default", "subnet-edge": "default"},
            "acl_rules": {"shared": [], "own-data": [], "own-edge": []}, "windows": None,
            "config": {"quarantine": False, "rg": "", "forensic": [], "readable": True}, **over}


def _check(m: AwsIsolationMachine):
    """Every invariant of the machine, as Hypothesis runs them after a step."""
    m.writes_only_its_own()
    m.never_more_open_than_designed()
    m.customer_configuration_untouched()
    m.every_entry_of_glorfindel_is_recorded()
    m.every_claim_is_true()
    m.one_vm_one_state_file()


def _run(monkeypatch, net, *steps, then=None):
    invariant_env(monkeypatch)
    m = AwsIsolationMachine()
    try:
        m.build(net)
        _check(m)
        for rule, *draws in steps:
            getattr(m, rule)(**({"data": Script(*draws)} if draws else {}))
            _check(m)
        if then:
            then(m)
    finally:
        m.teardown()


_ACL = "acl-default-vpc-a"
# AWS1 (#334): our block on i-web1 (its inbound deny at 99, under the default ACL's allow
# at 100), the inbound one turned into an allow by someone, the operator takes it off and
# the unblock the outbound one: number 99 is free on AWS again. The customer takes it.
_NUMBER_TAKEN_AGAIN = (
    ("block", "i-web1", None, 22, "vm"),
    ("tamper_with_our_entry", (_ACL, False, 99), "allow"),
    ("recover",),
    ("customer_adds_acl_entry", _ACL, "in-all", 99),
)


def test_an_entry_of_the_customer_at_a_number_glorfindel_once_held_is_the_customers(monkeypatch):
    """The fake keeps what Glorfindel wrote at (ACL, direction, number) after someone
    turned it around and the operator removed it — nothing deleted it through the API.
    The I2 oracle left out of the customer's entries any entry at such a key: the
    customer's own entry at the number freed, in the design, was missing from what the
    test read — « customer entries changed » on a world as the customer wrote it. Neither
    the fake (a free number is taken, as AWS does) nor the adapter (the unblock deletes
    only an entry still as it wrote it) was wrong. The oracle leaves out an entry by its
    content now: Glorfindel's as it wrote it, or what someone turned it into."""
    def then(m):
        assert m.fake.acls[_ACL]["entries"][(False, 99)]["action"] == "allow"
        assert (_ACL, False, 99) in m.fake.authored            # the stale record, kept
    _run(monkeypatch, _net(), *_NUMBER_TAKEN_AGAIN, then=then)


@pytest.mark.parametrize("change", ["deny", "gone"])
def test_the_oracle_sees_a_change_of_the_customers_entry_at_that_number(monkeypatch, change):
    """The other side of the same key: excluded by its key, the customer's entry at a
    number Glorfindel once held was out of I2's sight — turned into a deny, or deleted,
    by anyone but the customer, nothing said it. By content, I2 sees it (A0: the oracle
    refuses more, never less)."""
    def then(m):
        entries = m.fake.acls[_ACL]["entries"]
        if change == "deny":
            entries[(False, 99)] = dict(entries[(False, 99)], action="deny")
        else:
            del entries[(False, 99)]
        try:
            with pytest.raises(AssertionError, match="I2: customer entries of acl-default-vpc-a changed"):
                m.customer_configuration_untouched()
        finally:
            m.design["acls"][_ACL]["entries"].pop((False, 99))   # the teardown judges what is left
            entries.pop((False, 99), None)
    _run(monkeypatch, _net(), *_NUMBER_TAKEN_AGAIN, then=then)


def test_a_reisolation_of_an_eni_left_on_default_keeps_its_original(monkeypatch):
    """U2 on AWS (MC1, M606): i-web1 on its own group, isolated; someone takes eni-web1 out
    of the quarantine onto the VPC's `default` group (the analog of a NIC left bare, H2);
    Glorfindel isolates it again. What it carries then is `default`, not its original:
    the state keeps its own group, and the release puts that back. Recording `default`
    instead leaves it on `default` after a release that says « released » (I3).

    From the 0.5.9 release gate (MUT6): M606 survived both rounds with 500 examples (Hypothesis
    seeds 276700698 and 276700699) — the AWS machine reaches these steps only when its draw
    takes them in this order. Written by hand from the mutant's description, frozen so that
    M606 is caught on every run, whatever the seed."""
    def then(m):
        e = m.fake.enis["eni-web1"]
        assert e["groups"] == ["sg-default-vpc-a"] and e["design_groups"] == ["sg-own-eni-web1"]
        m.isolate(Script("i-web1", None))
        _check(m)
        out, _ = m._release("i-web1", None)          # I3: « released » is the design back
        assert out["status"] == "released" and e["groups"] == ["sg-own-eni-web1"]
    net = _net(groups={**{e: [] for e in _ENIS}, "eni-web1": ["own"]},
               config={"quarantine": True, "rg": "", "forensic": [], "readable": True})
    _run(monkeypatch, net, ("isolate", "i-web1", None), ("someone_detaches_the_quarantine", "eni-web1"), then=then)


def test_an_eni_left_on_default_whose_original_nothing_holds_is_released_on_default(monkeypatch):
    """I3 on AWS (AWS1b, #708): i-web2 on `default` and its own group, isolated — its
    original on the quarantine group's tag, the state never written (a full disk at the
    state write); someone takes eni-web2 out onto `default`; the tags of the quarantine
    group are lost. Nothing records its original any more: Glorfindel isolates it again
    from `default` and notes `default`, the release puts `default` back and says
    « released » — the AWS analog of a NIC left bare, re-isolated as bare (U2): the
    operator puts its group back.

    From the night of 10/11 (« Invariants (deep) », macOS, 10 000 examples, seed
    894570835): four failures, one sequence — I3 « release said released, not back to its
    design », and « verify_release True ». The oracle was wrong, not the adapter: once the
    re-isolation had written its state, the test read « a state held its original » from
    that `default`, where Azure's machine reads a record of « none » as nothing. A record
    of `default` learned from an ENI someone left there says nothing either."""
    def then(m):
        e, q = m.fake.enis["eni-web2"], m._ours_ids()[0]
        assert m._state("i-web2") is None and e["groups"] == [q]          # the fault hit the state write
        assert m.fake.sgs[q]["tags"]["glorfindel-orig-eni-web2"] == "sg-default-vpc-a,sg-own-eni-web2"
        m.someone_detaches_the_quarantine(Script("eni-web2"))
        _check(m)
        m.tags_lost(Script(q))
        _check(m)
        m.isolate(Script("i-web2", None))
        _check(m)
        assert [p["original_groups"] for p in m._state("i-web2")["placements"]] == [["sg-default-vpc-a"]]
        assert m._untraceable("i-web2", e) is False and "eni-web2" not in m.state_had   # in quarantine
        out, _ = m._release("i-web2", None)
        assert out["status"] == "released" and e["groups"] == ["sg-default-vpc-a"]
        m._check_claims("i-web2")                     # verify_release True on `default`: judged so
        _check(m)
    net = _net(groups={**{e: [] for e in _ENIS}, "eni-web2": ["default", "own"]},
               config={"quarantine": True, "rg": "", "forensic": [], "readable": True})
    _run(monkeypatch, net, ("isolate", "i-web2", (13, "before-429")), then=then)


def test_the_oracle_still_holds_an_original_a_state_had(monkeypatch):
    """The other side (A0: the oracle refuses more, never less): the same steps, the state
    written this time. After the tags are lost, the state still holds eni-web2's own
    original: traceable. The re-isolation from `default` keeps it (U2, M606), and the
    release puts both groups back — a release that left `default` alone would fail I3."""
    def then(m):
        e, q = m.fake.enis["eni-web2"], m._ours_ids()[0]
        m.someone_detaches_the_quarantine(Script("eni-web2"))
        m.tags_lost(Script(q))
        _check(m)
        assert m.state_had.get("eni-web2") == m.recorded_at["eni-web2"][0]
        assert m._untraceable("i-web2", e) is False
        m.isolate(Script("i-web2", None))
        _check(m)
        out, _ = m._release("i-web2", None)
        assert out["status"] == "released"
        assert sorted(e["groups"]) == ["sg-default-vpc-a", "sg-own-eni-web2"]
    net = _net(groups={**{e: [] for e in _ENIS}, "eni-web2": ["default", "own"]},
               config={"quarantine": True, "rg": "", "forensic": [], "readable": True})
    _run(monkeypatch, net, ("isolate", "i-web2", None), then=then)
