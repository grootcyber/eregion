"""SEC-H (#849): our rule names end with 128 bits of the NIC's id, and the names an earlier version
wrote (24 or 32 bits) are read, never trusted.

Two VMs named `web` in two groups, their NICs named `web-nic`, behind one subnet NSG: their ids meet
on the 6 hex of SHA-1 an earlier version ended the rule names with (found in a fraction of a second;
whoever can create a group and a NIC in the subscription finds one as fast). Under those names they
shared one name per rule: the release of one took off the other's deny, the isolation of one wrote
over the other's. Under ours they never meet. Placed before the upgrade, an isolation or a block under
the old names is still read (verified), and lifted through its state. Only what is proven is taken off
(Jonathan's decision, 19/11): a rule of an old name goes only when its VM's state records it on that NSG
for that NIC, its NIC's side names only addresses that placement recorded (L26) or the NIC holds, and no
other VM's state records it — the undo of a placement by its name included. Anything else is left and
said, with the command that takes it off by hand: a homonym's rule is never taken off by another's lift,
and an old isolation whose state is lost is taken off by hand (`_by_hand`, the operator's step).

On the in-memory Azure of tests/unit/fake_azure.py: 0 Azure call, 0 LLM call.
"""
from __future__ import annotations

import hashlib
import re

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
    and released now: the older name is A's too, but A's state doesn't record it — not proven A's.
    Left and said, A's release not done; B's deny stays."""
    f, c, s_nsg = world
    with monkeypatch.context() as m:
        m.setattr(NetworkMixin, "_placement_rule_base", _older_base)
        c.isolate_vm(B)
    b_rules = {n: dict(r) for n, r in _ours(f, s_nsg).items()}
    assert c.isolate_vm(A)["status"] == "isolated"
    out = c.release_isolation(A)
    assert out["status"] == "release_partial" and "laissée" in " ".join(out["failed"]), out
    assert "az network nsg rule delete" in " ".join(out["failed"])
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
    f.nics[key(B_NIC)]["ips"] = ["10.0.0.4"]      # its old address B's now: only the state says whose
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


def _by_hand(f, failed) -> list[str]:
    """The operator's step: each rule a lift left and said, taken off by the command it gives."""
    taken = []
    for text in failed or []:
        for rg, nsg, name in re.findall(r"az network nsg rule delete -g (\S+) --nsg-name (\S+) -n (\S+)", text):
            k = key(f"/subscriptions/s/resourceGroups/{rg}/providers/Microsoft.Network/networkSecurityGroups/{nsg}")
            if f.nsgs.get(k, {}).get("rules", {}).pop(name.rstrip(" ;,"), None) is not None:
                taken.append(name)
    return taken


def _lose_states() -> None:
    for d in (actions._ISOLATION_STATE_DIR, actions._BLOCK_STATE_DIR):
        for f in d.glob("*.json"):
            f.unlink()


def test_an_isolation_under_the_older_names_its_state_lost_is_left_and_said(world, monkeypatch):
    """No state to name them: nothing proves the older pair the NIC's — never taken off, said with
    the command; the verification never says released. The operator takes it off: then it is."""
    f, c, s_nsg = world
    with monkeypatch.context() as m:
        m.setattr(NetworkMixin, "_placement_rule_base", _older_base)
        c.isolate_vm(A)
    _lose_states()
    assert c.verify_isolation(A)["verified"] is True      # read under its older names: it isolates
    assert c.verify_release(A)["verified"] is not True
    out = c.release_isolation(A)
    assert out["status"] == "release_partial" and len(_ours(f, s_nsg)) == 2, out
    assert len(_by_hand(f, out["failed"])) == 2
    assert c.release_isolation(A)["status"] == "released"
    assert c.verify_release(A)["verified"] is True


def test_a_block_under_the_older_names_its_state_lost_is_left_and_said(world, monkeypatch):
    f, c, s_nsg = world
    with monkeypatch.context() as m:
        m.setattr(NetworkMixin, "_placement_rule_base", _older_base)
        c.block_suspicious_ip("203.0.113.7", A)
    _lose_states()
    assert c.verify_block_ip("203.0.113.7", A)["verified"] is True    # read under its older names: it blocks
    out = c.unblock_ip("203.0.113.7", A)
    assert out["status"] == "unblock_partial" and len(_ours(f, s_nsg)) == 2, out
    assert len(_by_hand(f, out["failed"])) == 2
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


# ── A NIC left bare, its NSG out of sight: what an earlier version left there ─────────────────

@pytest.fixture
def own_nsg_world(monkeypatch):
    """web's NIC on an NSG of its own, isolation by rules."""
    monkeypatch.setenv("GLORFINDEL_QUARANTINE_NSG", "0")
    f = FakeAzure()
    own = f.add_nsg(A_RG, "nsg-web-nic")
    subnet = f.add_subnet("rg-net", "vnet", "app", None)
    f.add_vm(A_RG, "web", [{"rg": A_RG, "name": "web-nic", "ips": ["10.0.0.4"], "subnet": subnet, "nsg": own}])
    c = AzureConnector(dry_run=False, read_only=False)
    c._network, c._compute = f.network, f.compute
    c._subscription_id = "s"
    c.recent_changes = lambda *a, **k: []
    return f, c, own


@pytest.mark.parametrize("lose", [True, False])
def test_an_older_isolation_on_the_nsg_a_bare_nic_left(own_nsg_world, monkeypatch, lose):
    """The review's sequence: an earlier version's isolation on the NIC's own NSG, someone takes that
    NSG off the NIC. Its state kept: proven, lifted. Its state lost: left and said — never `released`
    with the pair there, the VM cut off once its NSG comes back."""
    f, c, own = own_nsg_world
    with monkeypatch.context() as m:
        m.setattr(NetworkMixin, "_placement_rule_base", _older_base)
        assert c.isolate_vm(A)["status"] == "isolated"
    f.nics[key(A_NIC)]["nsg"] = None
    if lose:
        _lose_states()
    out = c.release_isolation(A)
    left = [n for n in f.nsgs[key(own)]["rules"] if n.startswith("glorfindel-")]
    if lose:
        assert out["status"] == "release_partial" and len(left) == 2, out
        assert "az network nsg rule delete" in " ".join(out["failed"])
    else:
        assert out["status"] == "released" and not left, out


def test_an_older_name_on_that_nsg_aimed_elsewhere_is_left_and_said(own_nsg_world, monkeypatch):
    """Under an older name but aimed at another address — a homonym's whose hash met, or ours moved by
    hand: whose it is can't be told. Left, said — never `released`."""
    f, c, own = own_nsg_world
    with monkeypatch.context() as m:
        m.setattr(NetworkMixin, "_placement_rule_base", _older_base)
        c.isolate_vm(A)
    rules = f.nsgs[key(own)]["rules"]
    for r in rules.values():
        for side in ("destination", "source"):
            if r.get(f"{side}_address_prefixes") == ["10.0.0.4"]:
                r[f"{side}_address_prefixes"] = ["10.0.0.99"]
    f.nics[key(A_NIC)]["nsg"] = None
    _lose_states()
    out = c.release_isolation(A)
    assert out["status"] == "release_partial" and "laissée" in " ".join(out["failed"]), out
    assert len([n for n in rules if n.startswith("glorfindel-")]) == 2


def test_two_long_ipv6_blocks_never_share_a_name():
    """A prefix with no room for the VM (an IPv6 block): the address kept as its own hash, one name
    per address — cut to the room, two neighbours took the same name."""
    c = AzureConnector()
    names = set()
    for ip in ("2001:db8:85a3:1111:2222:3333:4444:5555", "2001:db8:85a3:1111:2222:3333:4444:5556"):
        for base in c._placement_rule_bases(c._block_rule_prefix(ip), "web", "web-nic", A_NIC):
            assert len(f"{base}-out") <= 80 and base.endswith(_nic_mark(A_NIC)), base
            names.add(base)
    assert len(names) == 4


def test_a_gone_vms_older_pair_its_record_rewritten_is_left_and_said(world, monkeypatch):
    """The VM deleted, its record rewritten since under the new names: its older pair is looked for on
    every NSG — nothing records it any more, so nothing proves it the VM's. Left, said."""
    f, c, s_nsg = world
    with monkeypatch.context() as m:
        m.setattr(NetworkMixin, "_placement_rule_base", _older_base)
        c.isolate_vm(A)
    state = actions._load_isolation_state(A)
    new = c._placement_rule_base("glorfindel-iso", "web", "web-nic", A_NIC)
    for p in state["placements"]:
        p["rule_in"], p["rule_out"] = new, f"{new}-out"
    actions._save_isolation_state(A, state)
    for n in f.vms.pop(key(A))["nics"]:
        f.nics.pop(key(n))
    out = c.release_isolation(A)
    assert out["status"] == "release_partial" and len(_ours(f, s_nsg)) == 2, out


def test_a_gone_vms_older_pair_its_record_kept_is_lifted(world, monkeypatch):
    """Witness: the VM deleted, its record naming the older pair at its address: proven, lifted."""
    f, c, s_nsg = world
    with monkeypatch.context() as m:
        m.setattr(NetworkMixin, "_placement_rule_base", _older_base)
        c.isolate_vm(A)
    for n in f.vms.pop(key(A))["nics"]:
        f.nics.pop(key(n))
    assert c.release_isolation(A)["status"] == "released"
    assert not _ours(f, s_nsg)


@pytest.mark.parametrize("behind", ["nic", "subnet"])
@pytest.mark.parametrize("b_ip", ["10.0.0.4", "10.1.0.4"])
@pytest.mark.parametrize("path", ["away", "gone"])
def test_a_homonyms_older_pair_in_another_vnet_stays_whatever_its_address(monkeypatch, path, b_ip, behind):
    """The second review's sequence: B isolated by the earlier version on its NSG, in another VNet —
    often at the same private address as A (10.0.0.4) —, A isolated since, then left bare or deleted.
    A's release looks for its older names on NSGs it does not carry: B's pair, under the same name,
    aimed at an address B's NIC holds behind that NSG — B's. Left, said; B still isolated."""
    monkeypatch.setenv("GLORFINDEL_QUARANTINE_NSG", "0")
    f = FakeAzure()
    nsg_a, nsg_b = f.add_nsg(A_RG, "nsg-a"), f.add_nsg(B_RG, "nsg-b")
    # B behind nsg-b on its NIC, or on its subnet (`behind`).
    sa = f.add_subnet(A_RG, "vnet-a", "app", None)
    sb = f.add_subnet(B_RG, "vnet-b", "app", nsg_b if behind == "subnet" else None)
    f.add_vm(A_RG, "web", [{"rg": A_RG, "name": "web-nic", "ips": ["10.0.0.4"], "subnet": sa, "nsg": nsg_a}])
    f.add_vm(B_RG, "web", [{"rg": B_RG, "name": "web-nic", "ips": [b_ip], "subnet": sb,
                            "nsg": nsg_b if behind == "nic" else None}])
    c = AzureConnector(dry_run=False, read_only=False)
    c._network, c._compute = f.network, f.compute
    c._subscription_id = "s"
    c.recent_changes = lambda *a, **k: []
    with monkeypatch.context() as m:
        m.setattr(NetworkMixin, "_placement_rule_base", _older_base)
        assert c.isolate_vm(B)["status"] == "isolated"
    b_rules = {n: dict(r) for n, r in f.nsgs[key(nsg_b)]["rules"].items() if n.startswith("glorfindel-")}
    assert c.isolate_vm(A)["status"] == "isolated"
    if path == "away":
        f.nics[key(A_NIC)]["nsg"] = None
    else:
        for n in f.vms.pop(key(A))["nics"]:
            f.nics.pop(key(n))
    out = c.release_isolation(A)
    assert out["status"] == "release_partial" and "laissée" in " ".join(out["failed"]), out
    assert {n: r for n, r in f.nsgs[key(nsg_b)]["rules"].items() if n.startswith("glorfindel-")} == b_rules
    assert c.verify_isolation(B)["verified"] is True


@pytest.mark.parametrize("access", ["Deny", "Allow"])
def test_an_older_block_its_address_moved_and_its_state_lost_is_left_and_said(world, monkeypatch, access):
    """The machine's sequence (third review): a block under the older names, one of its rules turned
    into an allow, the NIC's address moved, the state lost — the unblock said `unblocked`, the pair left.
    Nothing proves it the NIC's now: left and said, the unblock not done."""
    f, c, s_nsg = world
    with monkeypatch.context() as m:
        m.setattr(NetworkMixin, "_placement_rule_base", _older_base)
        assert c.block_suspicious_ip("203.0.113.7", A)["status"] == "blocked"
    older = c._older_rule_bases(c._block_rule_prefix("203.0.113.7"), "web", "web-nic", A_NIC)[0]
    f.nsgs[key(s_nsg)]["rules"][older]["access"] = access
    f.nics[key(A_NIC)]["ips"] = ["10.0.0.9"]
    _lose_states()
    out = c.unblock_ip("203.0.113.7", A)
    assert out["status"] == "unblock_partial" and len(_ours(f, s_nsg)) == 2, out


def test_an_older_block_its_address_moved_its_state_kept_is_lifted(world, monkeypatch):
    """Witness (L26): the state records the pair and the address it had then — proven, lifted."""
    f, c, s_nsg = world
    with monkeypatch.context() as m:
        m.setattr(NetworkMixin, "_placement_rule_base", _older_base)
        c.block_suspicious_ip("203.0.113.7", A)
    f.nics[key(A_NIC)]["ips"] = ["10.0.0.9"]
    assert c.unblock_ip("203.0.113.7", A)["status"] == "unblocked"
    assert not _ours(f, s_nsg)


def test_a_rule_rewritten_under_its_older_name_at_other_addresses_stays(world, monkeypatch):
    """The third review's case (2): the state records the older name, but the rule under it was written
    again for other addresses (a homonym whose hash met, its isolation under the same name on a shared
    NSG): beyond the addresses the placement recorded and the NIC holds — not proven, left, said."""
    f, c, s_nsg = world
    with monkeypatch.context() as m:
        m.setattr(NetworkMixin, "_placement_rule_base", _older_base)
        c.isolate_vm(A)
    for r in f.nsgs[key(s_nsg)]["rules"].values():
        for side in ("destination", "source"):
            if r.get(f"{side}_address_prefixes") == ["10.0.0.4"]:
                r[f"{side}_address_prefixes"] = ["10.0.0.5"]
    out = c.sweep_vm_rules(A)
    assert out["status"] != "swept" and len(_ours(f, s_nsg)) == 2, out


def test_an_older_block_whose_address_another_live_nic_took_stays(world, monkeypatch):
    """The same, but the old address now another live NIC's behind that NSG (B moved there): whose the
    deny is can't be told — it stays (a homonym's, at that address, would lose its block)."""
    f, c, s_nsg = world
    with monkeypatch.context() as m:
        m.setattr(NetworkMixin, "_placement_rule_base", _older_base)
        c.block_suspicious_ip("203.0.113.7", A)
    f.nics[key(A_NIC)]["ips"] = ["10.0.0.9"]
    f.nics[key(B_NIC)]["ips"] = ["10.0.0.4"]
    _lose_states()
    c.unblock_ip("203.0.113.7", A)
    assert len(_ours(f, s_nsg)) == 2


def test_an_older_name_left_is_never_read_released(world, monkeypatch):
    """The third review's case (3): an older name the judge refuses, on an NSG that governs the NIC —
    left in silence, and the tools said « released, verified ». Said: the verification unknown, never
    True, its name given."""
    f, c, s_nsg = world
    with monkeypatch.context() as m:
        m.setattr(NetworkMixin, "_placement_rule_base", _older_base)
        c.isolate_vm(A)
    _lose_states()
    v = c.verify_release(A)
    older = c._older_rule_bases("glorfindel-iso", "web", "web-nic", A_NIC)[0]
    assert v["verified"] is not True and older in str(v), v


def _hub_world(monkeypatch, b_ip):
    """A and B, homonyms whose NICs meet on the older mark, on one NSG two VNets share (nsg-x)."""
    monkeypatch.setenv("GLORFINDEL_QUARANTINE_NSG", "0")
    f = FakeAzure()
    x = f.add_nsg("rg-hub", "nsg-x")
    sa, sb = f.add_subnet(A_RG, "vnet-a", "app", None), f.add_subnet(B_RG, "vnet-b", "app", None)
    f.add_vm(A_RG, "web", [{"rg": A_RG, "name": "web-nic", "ips": ["10.0.0.4"], "subnet": sa, "nsg": x}])
    f.add_vm(B_RG, "web", [{"rg": B_RG, "name": "web-nic", "ips": [b_ip], "subnet": sb, "nsg": x}])
    c = AzureConnector(dry_run=False, read_only=False)
    c._network, c._compute = f.network, f.compute
    c._subscription_id = "s"
    c.recent_changes = lambda *a, **k: []
    return f, c, x


def _older_both(c, monkeypatch, how: str = "isolate") -> None:
    with monkeypatch.context() as m:
        m.setattr(NetworkMixin, "_placement_rule_base", _older_base)
        for vm in (A, B):                      # B's under the same name: written over A's
            (c.isolate_vm(vm) if how == "isolate" else c.block_suspicious_ip("203.0.113.7", vm))


def _glorfindel(f, x) -> dict:
    return {n: dict(r) for n, r in f.nsgs[key(x)]["rules"].items() if n.startswith("glorfindel-")}


@pytest.mark.parametrize("b_ip", ["10.1.0.4", "10.0.0.4"])
def test_a_placement_written_over_by_a_homonym_is_not_undone_by_its_name(monkeypatch, b_ip):
    """The third review's case (probe 4): both isolated by the earlier version on one NSG, B's pair
    written over A's under the same name. A's release undid its placement by the name — B's pair went.
    The rule under it is no longer proven A's (other addresses, or another VM's state records it): left."""
    f, c, x = _hub_world(monkeypatch, b_ip)
    _older_both(c, monkeypatch)
    b_rules = _glorfindel(f, x)
    out = c.release_isolation(A)
    assert out["status"] == "release_partial" and "laissée" in " ".join(out["failed"]), out
    assert _glorfindel(f, x) == b_rules
    assert c.verify_isolation(B)["verified"] is True


def test_a_rule_another_vms_state_records_stays(monkeypatch):
    """Same name, same NSG, same address: the rule is either VM's — B's state records it too. The reset
    of A leaves it, said."""
    f, c, x = _hub_world(monkeypatch, "10.0.0.4")
    _older_both(c, monkeypatch)
    out = c.sweep_vm_rules(A)
    assert out["status"] == "swept_partial", out
    assert len(_glorfindel(f, x)) == 2


def test_a_block_placement_written_over_by_a_homonym_is_not_undone_by_its_name(monkeypatch):
    f, c, x = _hub_world(monkeypatch, "10.1.0.4")
    _older_both(c, monkeypatch, "block")
    b_rules = _glorfindel(f, x)
    out = c.unblock_ip("203.0.113.7", A)
    assert out["status"] == "unblock_partial" and "laissée" in " ".join(out["failed"]), out
    assert _glorfindel(f, x) == b_rules


@pytest.mark.parametrize("wide", ["*", None])
def test_an_older_rule_widened_to_every_address_stays(world, monkeypatch, wide):
    """Its state records it, but the rule under it now names every address (`*`, or no address on its
    side): beyond the addresses recorded — not proven, left."""
    f, c, s_nsg = world
    with monkeypatch.context() as m:
        m.setattr(NetworkMixin, "_placement_rule_base", _older_base)
        c.isolate_vm(A)
    for r in f.nsgs[key(s_nsg)]["rules"].values():
        for side in ("destination", "source"):
            if r.get(f"{side}_address_prefixes") == ["10.0.0.4"]:
                r[f"{side}_address_prefixes"] = None
                r[f"{side}_address_prefix"] = wide
    out = c.sweep_vm_rules(A)
    assert out["status"] != "swept" and len(_ours(f, s_nsg)) == 2, out