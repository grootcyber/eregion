"""SEC-H (#849): our rule names end with 128 bits of the NIC's id, and the names an earlier version
wrote (24 or 32 bits) are read, never trusted.

Two VMs named `web` in two groups, their NICs named `web-nic`, behind one subnet NSG: their ids meet
on the 6 hex of SHA-1 an earlier version ended the rule names with (found in a fraction of a second;
whoever can create a group and a NIC in the subscription finds one as fast). Under those names they
shared one name per rule: the release of one took off the other's deny, the isolation of one wrote
over the other's. Under ours they never meet. Placed before the upgrade, an isolation or a block under
the old names is still read (verified), and lifted through its state; a rule of an old name that is
not this NIC's — a homonym's whose hash met — stays.

On the in-memory Azure of tests/unit/fake_azure.py: 0 Azure call, 0 LLM call.
"""
from __future__ import annotations

import hashlib

import pytest

from glorfindel import actions
from glorfindel.actions import AzureConnector
from glorfindel.providers.azure.network import NetworkMixin
from glorfindel.providers.azure.nsg import _nic_hash, _nic_mark

from .fake_azure import FakeAzure, key, nic_id

A_RG, B_RG = "rg-2829", "rg-4727"          # web-nic's ids in these two groups meet on 6 hex
A = f"/subscriptions/s/resourceGroups/{A_RG}/providers/Microsoft.Compute/virtualMachines/web"
B = f"/subscriptions/s/resourceGroups/{B_RG}/providers/Microsoft.Compute/virtualMachines/web"
A_NIC, B_NIC = nic_id(A_RG, "web-nic"), nic_id(B_RG, "web-nic")


def _older_base(self, prefix: str, vm_name: str, nic_short: str, nic_id_: str) -> str:
    """The base an earlier version wrote (6 or 8 hex of SHA-1): to place what it placed."""
    return NetworkMixin._older_rule_bases(self, prefix, vm_name, nic_short, nic_id_)[0]


@pytest.fixture
def world(monkeypatch):
    """A and B behind one subnet NSG (no NSG of their own), isolation by rules."""
    monkeypatch.setenv("GLORFINDEL_QUARANTINE_NSG", "0")
    f = FakeAzure()
    s_nsg = f.add_nsg("rg-net", "nsg-subnet")
    subnet = f.add_subnet("rg-net", "vnet-hub", "app", s_nsg)
    f.add_vm(A_RG, "web", [{"rg": A_RG, "name": "web-nic", "ips": ["10.0.0.4"], "subnet": subnet, "nsg": None}])
    f.add_vm(B_RG, "web", [{"rg": B_RG, "name": "web-nic", "ips": ["10.0.0.5"], "subnet": subnet, "nsg": None}])
    c = AzureConnector(dry_run=False, read_only=False)
    c._network, c._compute = f.network, f.compute
    c._subscription_id = "s"
    c.recent_changes = lambda *a, **k: []
    return f, c, s_nsg


def _ours(f, s_nsg) -> dict:
    return {n: r for n, r in f.nsgs[key(s_nsg)]["rules"].items() if n.startswith("glorfindel-")}


def _covers(r: dict, ip: str) -> bool:
    values = [r.get("destination_address_prefix")] + list(r.get("destination_address_prefixes") or [])
    values += [r.get("source_address_prefix")] + list(r.get("source_address_prefixes") or [])
    return ip in [v for v in values if v]


def test_the_two_nics_meet_on_the_older_mark_never_on_ours():
    assert _nic_hash(A_NIC, 6) == _nic_hash(B_NIC, 6)
    assert _nic_mark(A_NIC) != _nic_mark(B_NIC) and len(_nic_mark(A_NIC)) == 32
    c = AzureConnector()
    assert c._placement_rule_base("glorfindel-iso", "web", "web-nic", A_NIC) != \
        c._placement_rule_base("glorfindel-iso", "web", "web-nic", B_NIC)
    assert c._older_rule_bases("glorfindel-iso", "web", "web-nic", A_NIC) == \
        c._older_rule_bases("glorfindel-iso", "web", "web-nic", B_NIC)


def test_the_release_of_one_never_takes_off_the_others_deny(world):
    """The lab's sequence (V-15): both isolated, A released — B's deny took the same name and went."""
    f, c, s_nsg = world
    assert c.isolate_vm(A)["status"] == "isolated"
    assert c.isolate_vm(B)["status"] == "isolated"
    assert len(_ours(f, s_nsg)) == 4                     # two pairs, never one name for two NICs
    assert c.release_isolation(A)["status"] == "released"
    left = _ours(f, s_nsg)
    assert len(left) == 2 and all(_covers(r, "10.0.0.5") for r in left.values()), left
    assert c.verify_isolation(B)["verified"] is True


def test_an_isolation_never_writes_over_the_others_rule(world):
    f, c, s_nsg = world
    c.isolate_vm(B)
    before = {n: dict(r) for n, r in _ours(f, s_nsg).items()}
    c.isolate_vm(A)
    assert {n: r for n, r in _ours(f, s_nsg).items() if n in before} == before


def test_every_name_fits_azures_80_characters():
    c = AzureConnector()
    long_vm = "vm-celebrimbor-gondolin-with-a-very-long-name-for-sure"
    for prefix in ("glorfindel-iso", "glorfindel-block-203-0-113-250", "glorfindel-block-2001-db8--1"):
        for vm, nic in (("web", "web-nic"), (long_vm, f"{long_vm}-nic")):
            for base in c._placement_rule_bases(prefix, vm, nic, A_NIC):
                assert len(f"{base}-out") <= 80, base
                assert base.endswith(_nic_mark(A_NIC)), base


# ── The migration: what an earlier version placed, read and lifted ──────────────────────────

def test_an_isolation_under_the_older_names_is_verified_then_lifted(world, monkeypatch):
    f, c, s_nsg = world
    with monkeypatch.context() as m:
        m.setattr(NetworkMixin, "_placement_rule_base", _older_base)
        assert c.isolate_vm(A)["status"] == "isolated"
    older = c._older_rule_bases("glorfindel-iso", "web", "web-nic", A_NIC)[0]
    assert set(_ours(f, s_nsg)) == {older, f"{older}-out"}
    assert c.verify_isolation(A)["verified"] is True       # read under its older name
    assert c.release_isolation(A)["status"] == "released"
    assert not _ours(f, s_nsg)
    assert actions._load_isolation_state(A) is None


def test_isolated_again_it_goes_under_the_new_names_and_both_are_lifted(world, monkeypatch):
    f, c, s_nsg = world
    with monkeypatch.context() as m:
        m.setattr(NetworkMixin, "_placement_rule_base", _older_base)
        c.isolate_vm(A)
    assert c.isolate_vm(A)["status"] == "isolated"
    new = c._placement_rule_base("glorfindel-iso", "web", "web-nic", A_NIC)
    assert {new, f"{new}-out"} <= set(_ours(f, s_nsg))
    assert c.release_isolation(A)["status"] == "released"
    assert not _ours(f, s_nsg)


def test_a_homonyms_rule_under_the_shared_older_name_stays(world, monkeypatch):
    """B isolated by an earlier version (its rules under the older name A's NIC meets), A isolated
    and released now: A's sweep reads the older name — B's deny, aimed at B — and leaves it."""
    f, c, s_nsg = world
    with monkeypatch.context() as m:
        m.setattr(NetworkMixin, "_placement_rule_base", _older_base)
        c.isolate_vm(B)
    b_rules = {n: dict(r) for n, r in _ours(f, s_nsg).items()}
    assert c.isolate_vm(A)["status"] == "isolated"
    assert c.release_isolation(A)["status"] == "released"
    assert {n: r for n, r in _ours(f, s_nsg).items()} == b_rules
    assert c.verify_isolation(B)["verified"] is True


def test_the_reset_lifts_an_older_name_its_state_records_after_the_address_moved(world, monkeypatch):
    """Its NIC given another address since: the older pair, aimed at the old one, no longer applies
    to the NIC — the state that records it says it is ours (L26)."""
    f, c, s_nsg = world
    with monkeypatch.context() as m:
        m.setattr(NetworkMixin, "_placement_rule_base", _older_base)
        c.isolate_vm(A)
    f.nics[key(A_NIC)]["ips"] = ["10.0.0.9"]
    out = c.sweep_vm_rules(A)
    assert out["status"] == "swept", out
    assert not _ours(f, s_nsg)


def test_a_block_under_the_older_names_is_verified_then_lifted(world, monkeypatch):
    f, c, s_nsg = world
    with monkeypatch.context() as m:
        m.setattr(NetworkMixin, "_placement_rule_base", _older_base)
        assert c.block_suspicious_ip("203.0.113.7", A)["status"] == "blocked"
    assert c.verify_block_ip("203.0.113.7", A)["verified"] is True
    assert c.unblock_ip("203.0.113.7", A)["status"] == "unblocked"
    assert not _ours(f, s_nsg)


def _lose_states() -> None:
    for d in (actions._ISOLATION_STATE_DIR, actions._BLOCK_STATE_DIR):
        for f in d.glob("*.json"):
            f.unlink()


def test_an_isolation_under_the_older_names_its_state_lost_is_still_found(world, monkeypatch):
    """No state to name them: the older names are read on the NIC's NSGs — verified, lifted (their
    denies apply to the NIC's addresses)."""
    f, c, s_nsg = world
    with monkeypatch.context() as m:
        m.setattr(NetworkMixin, "_placement_rule_base", _older_base)
        c.isolate_vm(A)
    _lose_states()
    assert c.verify_isolation(A)["verified"] is True
    assert c.release_isolation(A)["status"] == "released"
    assert not _ours(f, s_nsg)


def test_a_block_under_the_older_names_its_state_lost_is_still_found(world, monkeypatch):
    f, c, s_nsg = world
    with monkeypatch.context() as m:
        m.setattr(NetworkMixin, "_placement_rule_base", _older_base)
        c.block_suspicious_ip("203.0.113.7", A)
    _lose_states()
    assert c.verify_block_ip("203.0.113.7", A)["verified"] is True
    assert c.unblock_ip("203.0.113.7", A)["status"] == "unblocked"
    assert not _ours(f, s_nsg)


# ── The orphan sweep reads both marks ────────────────────────────────────────────────────────

def test_an_orphan_under_the_new_mark_is_found(world):
    f, c, s_nsg = world
    c.isolate_vm(A)
    gone = f.nics.pop(key(A_NIC))
    f.vms.pop(key(A), None)
    f.add_vm("rg-new", "batch", [{"rg": "rg-new", "name": "batch-nic", "ips": gone["ips"],
                                  "subnet": gone["subnet"], "nsg": None}])
    actions._clear_isolation_state(A)
    found = {o["rule"] for o in c.find_orphan_rules()}
    assert {n for n in _ours(f, s_nsg) if _nic_mark(A_NIC) in n} <= found


def test_a_live_nics_new_mark_is_never_an_orphan(world):
    f, c, s_nsg = world
    c.isolate_vm(A)
    assert not c.find_orphan_rules()


# ── The original's tag on the quarantine NSG ─────────────────────────────────────────────────

def test_the_original_is_kept_under_128_bits_and_read_under_the_older_key():
    c = AzureConnector()
    assert c._orig_tag(A_NIC) == "glorfindel-orig-" + hashlib.sha256(A_NIC.lower().encode()).hexdigest()[:32]
    assert c._older_orig_tag(A_NIC) == "glorfindel-orig-" + hashlib.sha1(A_NIC.lower().encode()).hexdigest()[:12]

    tags: dict = {c._older_orig_tag(A_NIC): "/subscriptions/s/resourceGroups/rg/providers/"
                                             "Microsoft.Network/networkSecurityGroups/nsg-x"}
    c._subscription_id = "s"
    c._quarantine_tags = lambda q: dict(tags)
    q = {"nsg_rg": "rg", "nsg_name": "nsg-glorfindel-quarantine-westeurope", "nsg_id": "q"}
    assert c._original_from_tags(q, A_NIC).endswith("/nsg-x")       # the earlier version's, read

    written = {}
    c._write_quarantine_tags = lambda q, t: (written.clear(), written.update(t), tags.clear(), tags.update(t))
    c._record_original(q, A_NIC, None)
    assert written == {c._orig_tag(A_NIC): "none"}                   # ours written, the older one gone
    tags[c._older_orig_tag(A_NIC)] = "none"
    c._forget_original(q, A_NIC)
    assert not set(tags) & c._orig_tags(A_NIC)
