"""SEC2c (#1107): the exposed zone — `network_zones.exposed`, a block of ONE host possible again there, the
attacked VM's mode permitting; the order of the layers; the expiry at 24 h and the lift once another VM holds
the address, by the watch, said; the declaration said loud at the start; the review of SEC2b's six points.

The client's network is the store the discovery writes (glorfindel/client_network.py, under the conftest's
tmp home), written here from a read as the adapter returns it. The block and its lift go through the Azure
connector on the in-memory Azure (tests/unit/fake_azure.py): the lift takes off the block's rules, and only
them. Every identifier is made up (repository public): documentation addresses (RFC 5737, RFC 3849),
example names. No Azure, no model.
"""
from __future__ import annotations

import logging
from datetime import datetime, timedelta, timezone
from unittest.mock import patch

import pytest

from glorfindel import client_network as cn
from glorfindel import client_network_watch as cnw
from glorfindel import config, escalations, exposed_blocks
from glorfindel.exposed_zone import EXPIRY_S
from glorfindel.response.policy import (
    CLIENT, EXPOSED, NEVER_BLOCK, ProtectedAddressError, blockable_ip, held_words, protection,
)

from .fake_azure import FakeAzure, key, vm_id

SUB = "/subscriptions/00000000-0000-0000-0000-000000000000"
NET = f"{SUB}/resourceGroups/rg-net/providers/Microsoft.Network"
DMZ = "203.0.113.0/26"           # a subnet of the client's VNet, outside the private ranges
HOST = "203.0.113.40"            # one VM of the DMZ
FW = "203.0.113.50"              # an appliance's address (its NIC forwards packets)
TWICE = "203.0.113.45"           # held by two VMs (two VNets reuse it)
FRONT = "203.0.113.10"           # a load balancer's private frontend
PARTNER = "198.51.100.0/24"      # a partner's range, beside the client's public IPs
NAT_IP = "198.51.100.20"         # the client's NAT gateway
WEB_IP = "198.51.100.30"         # a VM's public IP (one host)
FW_IP = "198.51.100.31"          # the appliance's public IP
OUT = "198.51.100.200"           # the partner's host: nobody's in Azure
INTERNET = "192.0.2.77"


def _vm(name: str) -> str:
    return f"{SUB}/resourceGroups/rg-app/providers/Microsoft.Compute/virtualMachines/{name}"


def _nic(name: str, vm: str, ips: list[str], forwarding: bool = False) -> dict:
    return {"id": f"{NET}/networkInterfaces/{name}", "vm": _vm(vm), "forwarding": forwarding, "private_ips": ips}


def _read(nics: list[dict] | None = None) -> dict:
    """The client's network as the adapter reads it (providers/azure/client_network.py)."""
    return {
        "vnets": [{"id": f"{NET}/virtualNetworks/vnet-hub", "name": "vnet-hub",
                   "prefixes": ["10.1.0.0/16", "203.0.113.0/24"],
                   "subnets": [{"name": "snet-dmz", "prefixes": [DMZ]},
                               {"name": "snet-app", "prefixes": ["10.1.1.0/24"]}]},
                  {"id": f"{NET}/virtualNetworks/vnet-big", "name": "vnet-big", "prefixes": ["10.16.0.0/12"],
                   "subnets": []}],
        "public_ips": [
            {"id": f"{NET}/publicIPAddresses/pip-nat", "address": NAT_IP, "kind": "nat_gateway",
             "attached_to": f"{NET}/natGateways/nat-out"},
            {"id": f"{NET}/publicIPAddresses/pip-web", "address": WEB_IP, "kind": "nic",
             "attached_to": f"{NET}/networkInterfaces/nic-web"},
            {"id": f"{NET}/publicIPAddresses/pip-fw", "address": FW_IP, "kind": "nic",
             "attached_to": f"{NET}/networkInterfaces/nic-fw"}],
        "prefixes": [{"id": f"{NET}/publicIPPrefixes/pfx", "prefix": "198.51.100.64/28", "kind": "other",
                      "attached_to": ""}],
        "frontends": [{"id": f"{NET}/loadBalancers/lb-dmz/frontendIPConfigurations/fe", "address": FRONT,
                       "lb": f"{NET}/loadBalancers/lb-dmz"}],
        "nics": nics if nics is not None else [
            _nic("nic-dmz", "vm-dmz", [HOST]), _nic("nic-web", "vm-web", ["10.1.1.4"]),
            _nic("nic-fw", "vm-fw", [FW], forwarding=True),
            _nic("nic-a", "vm-a", [TWICE]), _nic("nic-b", "vm-b", [TWICE])],
        "unread": [],
    }


@pytest.fixture
def cfg_file(tmp_path, monkeypatch):
    path = tmp_path / "glorfindel-config.yaml"
    monkeypatch.setattr(config, "_DEFAULT_PATHS", [path])
    path.write_text(f"network_zones:\n  exposed: [{DMZ}, {PARTNER}]\n")
    return path


def _saved(read: dict | None = None, at: datetime | None = None) -> cn.Snapshot:
    return cn.save(read or _read(), at or datetime.now(timezone.utc), config.load_glorfindel_config().networks)


def _cards(kind: str) -> list[dict]:
    return [e for e in escalations.pending() if e["escalation_type"] == kind]


# ── The key, read strictly ───────────────────────────────────────────────────────────────────

def test_the_exposed_zone_is_read_its_names_cited_where_they_serve(cfg_file):
    cfg_file.write_text("networks:\n  dmz: {subnet: vnet-hub/snet-dmz}\n  partenaire: [198.51.100.0/25]\n"
                        f"network_zones:\n  exposed: [dmz, partenaire, {OUT}]\n")
    cfg = config.load_glorfindel_config()
    assert cfg.exposed == ["198.51.100.0/25", f"{OUT}/32"] and cfg.exposed_names == ["dmz", "partenaire"]
    assert cfg.network_uses == {"dmz": ["network_zones.exposed"], "partenaire": ["network_zones.exposed"]}
    assert cfg.notes == []


@pytest.mark.parametrize("entry,said", [
    ("10.0.0.0/15", "plus large que /16"),                                      # M7182
    ("2001:db8::/47", "plus large que /48"),
    ("168.63.129.16/32", "plateforme Azure"),                                   # M7183
    ("169.254.0.0/24", "touche 169.254.0.0/16"),
    ("127.0.0.0/24", "touche 127.0.0.0/8"),
    ("::ffff:198.51.100.0/120", "touche ::ffff:0:0/96"),
    ("dmz", "aucun réseau nommé « dmz » déclaré"),
    ("203.0.113.1/26", "bits d'hôte"),
])
def test_a_zone_too_wide_on_the_platform_or_unknown_refuses_the_file(entry, said, cfg_file):
    """M7182, M7183: narrow, never the platform nor the loopback; a name not declared, host bits."""
    cfg_file.write_text(f"network_zones:\n  exposed: [\"{entry}\"]\n")
    with pytest.raises(config.ConfigError, match="network_zones.exposed") as err:
        config.load_glorfindel_config()
    assert said in str(err.value)


def test_the_ceiling_admits_a_sixteen_and_a_named_range_is_held_to_it(cfg_file):
    cfg_file.write_text("network_zones:\n  exposed: [10.0.0.0/16, \"2001:db8::/48\"]\n")
    assert config.load_glorfindel_config().exposed == ["10.0.0.0/16", "2001:db8::/48"]
    cfg_file.write_text("networks:\n  large: [10.0.0.0/8]\nnetwork_zones:\n  exposed: [large]\n")
    with pytest.raises(config.ConfigError, match="réseau nommé « large », 10.0.0.0/8 : plus large que /16"):
        config.load_glorfindel_config()


@pytest.mark.parametrize("text,said", [
    # SEC2d (#1147) reads expected_origins: tests/unit/test_lateral.py.
    ("network_zones:\n  exposed: []\n", "une liste vide ne déclare aucune zone"),
    ("network_zones:\n  exposd: [203.0.113.0/26]\n", "vouliez-vous dire « exposed »"),
])
def test_the_other_keys_of_network_zones_refuse_the_file(text, said, cfg_file):
    cfg_file.write_text(text)
    with pytest.raises(config.ConfigError, match=said):
        config.load_glorfindel_config()


# ── One host blockable, nothing else (decision 6) ────────────────────────────────────────────

@pytest.mark.parametrize("ip", [HOST, WEB_IP, OUT])
def test_one_host_of_the_zone_is_blockable_again(ip, cfg_file):
    """M7184: a VM of the DMZ, a VM's public IP, a partner's host nobody holds in Azure."""
    _saved()
    assert protection(ip).layer == EXPOSED
    assert blockable_ip(ip) == ip
    assert held_words(ip) == ""


@pytest.mark.parametrize("ip,said", [
    (NAT_IP, "passerelle NAT"),                                                 # M7185
    (FRONT, "frontal privé de l'équilibreur lb-dmz"),
    ("198.51.100.70", "préfixe public pfx"),
    (FW, "appliance"),                                                          # M7186
    (FW_IP, "appliance"),
    (TWICE, "tenue par 2 VM"),
    ("203.0.113.1", "réservée par Azure dans le sous-réseau vnet-hub/snet-dmz"),
    ("203.0.113.63", "réservée par Azure"),
    ("198.51.100.0", "adresse de réseau ou de diffusion de la zone"),
])
def test_what_is_no_single_host_stays_the_client_s_network(ip, said, cfg_file):
    """M7185, M7186: a NAT gateway, a frontend, a prefix, an appliance, an address of two VMs, an address Azure
    reserves — held as the client's network: a card for a human, the connector refusing it."""
    _saved()
    p = protection(ip)
    assert p.layer == CLIENT and said in p.source and p.source.startswith("zone exposée")
    with pytest.raises(ProtectedAddressError, match="réseau du client"):
        blockable_ip(ip)
    assert said in held_words(ip)


@pytest.mark.parametrize("make", [
    lambda: None,                                                                                  # never read
    lambda: _saved(at=datetime.now(timezone.utc) - timedelta(seconds=cn.MAX_AGE_S + 60)),         # too old
    lambda: _saved({**_read(), "unread": [{"what": "cartes réseau", "key": "nics", "error": "429"}]}),
])
def test_a_list_that_can_t_be_trusted_keeps_the_zone_protected(make, cfg_file):
    """M7187 (decision 4): never a block outside the Internet — the zone's partner host included, which the
    Internet's rule would have blocked: declared, it is no address of the Internet."""
    make()
    for ip in (HOST, OUT):
        p = protection(ip)
        assert p.layer == CLIENT and "non fiable" in p.source and p.degraded
        with pytest.raises(ProtectedAddressError, match="réseau du client"):
            blockable_ip(ip)


def test_a_store_an_older_version_wrote_judges_no_single_host(cfg_file):
    """No `nics` in the store (SEC2b's): an appliance can't be told — held until the next read."""
    _saved()
    import json
    body = json.loads(cn._STORE.read_text())
    del body["nics"]
    cn._STORE.write_text(json.dumps(body))
    assert cn.load().state == "fresh"
    assert "sans nics" in protection(HOST).source and protection(HOST).layer == CLIENT


# ── The order (decision 8) ───────────────────────────────────────────────────────────────────

def test_never_block_wins_over_the_zone_and_the_zone_over_the_client_s_network(cfg_file):
    """M7188: never_block before the zone; the zone before the VNet that holds it."""
    cfg_file.write_text(f"never_block: [{OUT}]\nnetwork_zones:\n  exposed: [{DMZ}, {PARTNER}]\n")
    _saved()
    assert protection(OUT).layer == NEVER_BLOCK
    with pytest.raises(ProtectedAddressError, match="never_block"):
        blockable_ip(OUT)
    assert (protection(HOST).layer, protection(HOST).entry) == (EXPOSED, DMZ)
    assert protection("203.0.113.200").layer == CLIENT                          # the VNet, outside the zone


def test_the_aws_connector_never_plays_the_zone(cfg_file):
    """No discovery of the VPCs: the zone skipped — a private address stays refused, a public one is the
    Internet's as before (no deadline)."""
    from glorfindel.response.policy import exposed_applies
    _saved()
    assert not exposed_applies("arn:aws:ec2:eu-west-1:123456789012:instance/i-0abc") and exposed_applies(_vm("x"))
    with pytest.raises(ProtectedAddressError, match="réseau du client"):
        blockable_ip(HOST, exposed=False)
    assert blockable_ip(OUT, exposed=False) == OUT and protection(OUT, exposed=False).layer == ""
    assert "réseau du client" in held_words(HOST, "arn:aws:ec2:eu-west-1:123456789012:instance/i-0abc")
    from glorfindel.providers.aws import blocks as aws_blocks
    with pytest.raises(ProtectedAddressError, match="réseau du client"):
        aws_blocks.blockable_ip(HOST)                                        # the connector's own judgement
    assert aws_blocks.blockable_ip(OUT) == OUT


# ── The mode decides, as for the Internet (decision 6) ───────────────────────────────────────

def test_decide_lets_the_mode_decide_a_block_of_one_exposed_host(cfg_file):
    """M7189: human_only never blocks alone — the mode's card, never the protected address's; non_disruptive
    runs it. A NAT gateway's address of the zone stays the protected address's card in either mode."""
    from glorfindel.agent import decide
    from glorfindel.config import AutonomyConfig
    from .test_agent_nodes import _mock_llm_response
    from .test_forged_logs import _block_state
    _saved()

    def decided(ip, mode):
        with patch("litellm.completion", return_value=_mock_llm_response("block_suspicious_ip", confidence=0.99)):
            return decide(_block_state(ip), model="claude-test", autonomy=AutonomyConfig(default=mode))
    held = decided(HOST, "human_only")
    assert held["escalate"] is True and held.get("held_by") != "never_block"
    assert "human_only" in held["escalation_reason"]
    ran = decided(HOST, "non_disruptive")
    assert ran["escalate"] is False and ran["action"] == "block_suspicious_ip", ran
    for mode in ("human_only", "non_disruptive"):
        nat = decided(NAT_IP, mode)
        assert nat["escalate"] is True and nat["held_by"] == "never_block"


# ── The block, its deadline, its lift (decision 7) ───────────────────────────────────────────

@pytest.fixture
def azure(monkeypatch):
    """A VM behind its NIC's NSG on the in-memory Azure, and the connector on it."""
    from glorfindel.actions import AzureConnector
    f = FakeAzure()
    nsg = f.add_nsg("rg-app", "nsg-web")
    subnet = f.add_subnet("rg-net", "vnet", "app", None)
    f.add_vm("rg-app", "web", [{"rg": "rg-app", "name": "web-nic", "ips": ["10.0.0.4"], "subnet": subnet,
                                 "nsg": nsg}])
    monkeypatch.setenv("AZURE_SUBSCRIPTION_ID", "s")
    c = AzureConnector(dry_run=False, read_only=False)
    c._network, c._compute = f.network, f.compute
    c._subscription_id = "s"
    return f, c, nsg


def _rules(f, nsg) -> dict:
    return {n: dict(r) for n, r in f.nsgs[key(nsg)]["rules"].items()}


def _entry(ip: str) -> dict:
    from glorfindel.actions import _load_block_entries
    return next((e for e in _load_block_entries(vm_id("rg-app", "web")) if e["ip"] == ip), {})


def test_a_block_of_the_zone_carries_its_deadline_and_who_held_the_address(cfg_file, azure):
    """M7190: written in the block's entry — the deadline outlives a restart; an Internet block has none."""
    f, c, _ = azure
    _saved()
    before = datetime.now(timezone.utc)
    c.block_suspicious_ip(HOST, vm_id("rg-app", "web"))
    c.block_suspicious_ip(INTERNET, vm_id("rg-app", "web"))
    mark = _entry(HOST)["exposed"]
    assert mark["zone"] == DMZ and mark["holder"] == _vm("vm-dmz").lower()
    expires = datetime.fromisoformat(mark["expires_at"])
    assert timedelta(seconds=EXPIRY_S) <= expires - before < timedelta(seconds=EXPIRY_S + 60)
    assert "exposed" not in _entry(INTERNET)
    c.block_suspicious_ip(HOST, vm_id("rg-app", "web"))                      # written again: same deadline
    assert _entry(HOST)["exposed"] == mark


def _customer(name: str, priority: int, access: str, port: str = "*"):
    from types import SimpleNamespace
    return SimpleNamespace(name=name, priority=priority, protocol="Tcp", source_port_range="*",
                           direction="Inbound", access=access, source_address_prefix=HOST,
                           destination_address_prefix="*", destination_port_range=port)


def test_the_watch_lifts_the_block_at_24_h_and_only_its_rules(cfg_file, azure):
    """M7191, a sequence frozen for the invariants (I-lift): the autonomous lift takes off the block's rules
    and nothing else — the customer's own deny and allow of that address, another VM's block of the same
    address on the same NSG (written as an Internet one, before the zone was declared), this VM's block of
    an Internet address: all as they were —, said on a card; a new connector (a restart) reads the deadline
    from the entry."""
    from glorfindel.actions import AzureConnector, _load_block_entries
    from .fake_azure import _rule_record
    f, c, nsg = azure
    for r in (_customer("client-deny-dmz", 3000, "Deny", "22"), _customer("client-allow-dmz", 3010, "Allow", "443")):
        f._put_rule(f.nsgs[key(nsg)], _rule_record(r))
    subnet = next(iter(f.subnets.values()))["id"]
    f.add_vm("rg-app", "api", [{"rg": "rg-app", "name": "api-nic", "ips": ["10.0.0.5"], "subnet": subnet,
                                 "nsg": nsg}])
    cfg_file.write_text("")                                       # no zone yet: api's block is an Internet one
    c.block_suspicious_ip(HOST, vm_id("rg-app", "api"))
    cfg_file.write_text(f"network_zones:\n  exposed: [{DMZ}, {PARTNER}]\n")
    _saved()
    c.block_suspicious_ip(INTERNET, vm_id("rg-app", "web"))
    before = _rules(f, nsg)
    assert {"client-deny-dmz", "client-allow-dmz"} <= set(before) and len(before) == 6
    c.block_suspicious_ip(HOST, vm_id("rg-app", "web"))
    assert _rules(f, nsg) != before
    api_entry = next(e for e in _load_block_entries(vm_id("rg-app", "api")) if e["ip"] == HOST)
    assert "exposed" not in api_entry
    deadline = datetime.fromisoformat(_entry(HOST)["exposed"]["expires_at"])
    assert exposed_blocks.expiry_pass(c, deadline - timedelta(hours=1)) == []
    restarted = AzureConnector(dry_run=False, read_only=False)
    restarted._network, restarted._compute, restarted._subscription_id = f.network, f.compute, "s"
    [r] = exposed_blocks.expiry_pass(restarted, deadline + timedelta(seconds=1))
    assert r["outcome"] == "lifted" and "échéance de 24 h" in r["why"]
    assert _rules(f, nsg) == before and _entry(HOST) == {} and _entry(INTERNET)
    [card] = _cards(exposed_blocks.LIFTED_TYPE)
    assert f"Blocage de {HOST} sur web levé seul" in card["reason"] and card["action_params"] == {"ip": HOST}
    assert exposed_blocks.expiry_pass(c, deadline + timedelta(hours=2)) == []   # the Internet's: never
    assert _rules(f, nsg) == before


def test_a_block_taken_again_since_is_never_lifted_on_the_old_deadline(cfg_file, azure):
    """M7203: judged due, then — before the lock — lifted by a human and taken again by a detection (a new
    entry, 24 h new): under the lock the entry is read and judged again, the new block left."""
    from glorfindel.actions import _clear_block_state
    f, c, nsg = azure
    _saved()
    c.block_suspicious_ip(HOST, vm_id("rg-app", "web"))
    [old] = exposed_blocks.marked()
    late = datetime.fromisoformat(old["exposed"]["expires_at"]) + timedelta(minutes=1)
    assert exposed_blocks.due(old, late, cn.load())
    c.unblock_ip(HOST, vm_id("rg-app", "web"))
    _clear_block_state(vm_id("rg-app", "web"), HOST)
    with patch("glorfindel.exposed_zone.datetime") as clock:
        clock.now.return_value = late
        c.block_suspicious_ip(HOST, vm_id("rg-app", "web"))
    assert _entry(HOST)["exposed"] != old["exposed"]
    r = exposed_blocks._lift(c, old, "échéance de 24 h atteinte", late, cn.load())
    assert r["outcome"] == "renewed" and _entry(HOST) and _cards(exposed_blocks.LIFTED_TYPE) == []


def test_a_block_written_over_a_failed_lift_takes_a_deadline_of_its_own(cfg_file, azure):
    """M7204: the lift failed, its deadline past; a new block written whole over that entry is a new episode
    — judged anew, 24 h new —, never lifted at the next pass on the past deadline."""
    from glorfindel.actions import _update_block_entry
    f, c, nsg = azure
    _saved()
    c.block_suspicious_ip(HOST, vm_id("rg-app", "web"))
    past = dict(_entry(HOST)["exposed"], expires_at=(datetime.now(timezone.utc) - timedelta(hours=1)).isoformat())
    _update_block_entry(vm_id("rg-app", "web"), HOST, exposed=past)
    f.write_denied = True
    [r] = exposed_blocks.expiry_pass(c)
    assert r["outcome"] == "failed" and _entry(HOST)["exposed"] == past
    f.write_denied = False
    c.block_suspicious_ip(HOST, vm_id("rg-app", "web"))
    assert datetime.fromisoformat(_entry(HOST)["exposed"]["expires_at"]) > datetime.now(timezone.utc)
    assert exposed_blocks.expiry_pass(c) == [] and _entry(HOST)


# ── One host, only on a proof (the review of SEC2c) ─────────────────────────────────────────

def _azure_services_read() -> dict:
    """The review's case: a VNet of the zone holding Azure Firewall's and Bastion's subnets, a subnet of
    VMs, and no NIC the listing reads in any of them."""
    read = _read(nics=[_nic("nic-dmz", "vm-dmz", ["203.0.113.140"])])
    read["vnets"] = [{"id": f"{NET}/virtualNetworks/vnet-edge", "name": "vnet-edge", "prefixes": ["203.0.113.0/24"],
                      "subnets": [{"name": "AzureFirewallSubnet", "prefixes": ["203.0.113.0/26"]},
                                  {"name": "AzureBastionSubnet", "prefixes": ["203.0.113.64/26"]},
                                  {"name": "snet-vms", "prefixes": ["203.0.113.128/26"]}]}]
    return read


@pytest.mark.parametrize("ip,said", [
    ("203.0.113.4", "AzureFirewallSubnet, réservé par Azure"),                 # M7201
    ("203.0.113.68", "AzureBastionSubnet, réservé par Azure"),
    ("203.0.113.150", "aucune carte réseau connue ne la tient"),                # M7200
    ("203.0.113.200", "hors de tout sous-réseau lu"),                           # M7205
])
def test_an_address_no_known_nic_holds_is_never_one_host(ip, said, cfg_file):
    """Azure Firewall's, Bastion's, a VPN gateway's private addresses, an Application Gateway's private
    frontend, a uniform scale set's instances: on no NIC of the listing — never « one host »."""
    cfg_file.write_text("network_zones:\n  exposed: [203.0.113.0/24, 198.51.100.0/24]\n")
    _saved(_azure_services_read())
    p = protection(ip)
    assert p.layer == CLIENT and said in p.source, p
    with pytest.raises(ProtectedAddressError, match="réseau du client"):
        blockable_ip(ip)
    assert protection("203.0.113.140").layer == EXPOSED                        # a NIC holds it: one host
    assert protection(OUT).layer == EXPOSED                                    # outside every VNet: the partner's


def test_the_connector_never_writes_a_block_of_the_zone_without_its_deadline(cfg_file, azure, monkeypatch):
    """M7202: judged twice (the connector keeps blockable_ip, then mark) — the second judgement failing, or
    holding the address back, refuses the block before any write: never an Internet block in its place."""
    from glorfindel.response import policy
    f, c, nsg = azure
    _saved()
    before, real = _rules(f, nsg), policy.protection
    for second in (lambda *a, **k: (_ for _ in ()).throw(OSError("disk")),
                   lambda ip, **k: real(ip, snap=cn.Snapshot(state="absent"))):
        calls = []

        def judged(ip, *a, second=second, **k):
            calls.append(ip)
            return real(ip, *a, **k) if len(calls) == 1 else second(ip, **k)
        monkeypatch.setattr(policy, "protection", judged)
        with pytest.raises(ProtectedAddressError, match="refusé"):
            c.block_suspicious_ip(HOST, vm_id("rg-app", "web"))
        assert _rules(f, nsg) == before and _entry(HOST) == {}
    monkeypatch.setattr(policy, "protection", real)
    c.block_suspicious_ip(INTERNET, vm_id("rg-app", "web"))                   # an Internet one: as before
    assert "exposed" not in _entry(INTERNET)


def test_the_block_is_lifted_once_another_vm_holds_the_address(cfg_file, azure):
    """M7192: the discovery reads HOST on another VM — lifted before the deadline; a list too old tells no
    holder: the deadline alone."""
    f, c, nsg = azure
    _saved()
    c.block_suspicious_ip(HOST, vm_id("rg-app", "web"))
    moved = _read([_nic("nic-new", "vm-new", [HOST])])
    _saved(moved, at=datetime.now(timezone.utc) - timedelta(seconds=cn.MAX_AGE_S + 60))
    assert exposed_blocks.expiry_pass(c) == []
    _saved(moved)
    [r] = exposed_blocks.expiry_pass(c)
    assert r["outcome"] == "lifted" and "passée à une autre VM (vm-new, tenue avant par vm-dmz)" in r["why"]
    assert _entry(HOST) == {}


def test_a_lift_that_fails_is_said_kept_and_tried_again(cfg_file, azure):
    """M7193: Azure refuses (403) — the entry kept, its rules still blocking, one card while it lasts; the
    next pass that passes lifts it and closes that card."""
    f, c, nsg = azure
    _saved()
    c.block_suspicious_ip(HOST, vm_id("rg-app", "web"))
    late = datetime.fromisoformat(_entry(HOST)["exposed"]["expires_at"]) + timedelta(minutes=1)
    f.write_denied = True
    for _ in range(2):
        [r] = exposed_blocks.expiry_pass(c, late)
        assert r["outcome"] == "failed"
    assert _entry(HOST).get("unblock_failed")
    [card] = _cards(exposed_blocks.FAILED_TYPE)
    assert card["occurrences"] == 2 and card["severity"] == "high" and "retente" in card["reason"]
    f.write_denied = False
    [r] = exposed_blocks.expiry_pass(c, late)
    assert r["outcome"] == "lifted" and _entry(HOST) == {}
    assert _cards(exposed_blocks.FAILED_TYPE) == [] and len(_cards(exposed_blocks.LIFTED_TYPE)) == 1


def test_a_deadline_that_can_t_be_read_is_a_deadline_past(cfg_file):
    entry = {"ip": HOST, "exposed": {"expires_at": "demain"}}
    assert "échéance illisible" in exposed_blocks.due(entry, datetime.now(timezone.utc), cn.load())


def test_list_says_the_deadline_of_a_block_of_the_zone():
    now = datetime(2026, 11, 23, 12, 0, tzinfo=timezone.utc)
    entry = {"exposed": {"zone": DMZ, "expires_at": "2026-11-24T12:00:00+00:00"}}
    assert exposed_blocks.said(entry, now) == f"  · zone exposée {DMZ}, levé seul le 2026-11-24 12:00 UTC (dans 24.0 h)"
    assert exposed_blocks.said({"ip": INTERNET}, now) == ""


def test_the_watch_runs_the_expiry_every_minute_in_its_own_thread(cfg_file):
    from pathlib import Path
    from glorfindel.watch.housekeeping import Housekeeping
    root = Path(__file__).resolve().parents[2]
    assert "hk._expire_exposed," in (root / "glorfindel" / "watch" / "loop.py").read_text()
    hk = Housekeeping.__new__(Housekeeping)
    hk.dry_run, hk.console, hk._output_lock = False, None, None
    started = []
    hk._expiry_thread = type("T", (), {"busy": lambda self: False, "start": lambda self, t: started.append(t)})()
    hk._expire_exposed()
    assert started == []                                    # nothing recorded: no thread, no Azure call
    with patch.object(exposed_blocks, "marked", return_value=[{"ip": HOST}]):
        hk._expire_exposed()
    assert started == [hk._expiry_run]


# ── Said loud at the start ───────────────────────────────────────────────────────────────────

def test_the_watch_says_each_zone_loud_at_its_start(cfg_file):
    """M7194: each range, what it allows, its deadline, what it holds that is no single host; the note of
    decision 6 for a zone in the private ranges; a named object too wide, left out; off while not trusted."""
    cfg_file.write_text("networks:\n  big: {vnet: vnet-big}\n"
                        f"network_zones:\n  exposed: [{DMZ}, {PARTNER}, 10.2.0.0/24, big]\n")
    cfg = config.load_glorfindel_config()
    loud = [t for lvl, t in cnw.start_lines(cfg) if lvl == "loud"]
    assert any("Zone exposée sans effet" in t for t in loud)                  # never read
    _saved()
    lines = cnw.start_lines(cfg)
    strong = [t for lvl, t in lines if lvl == "strong"]
    assert any(t.startswith(f"Zone exposée {DMZ} (zone exposée) — sert : network_zones.exposed") for t in strong)
    assert all("levé seul au bout de 24 h" in t for t in strong) and len(strong) == 3
    notes = [t for lvl, t in lines if lvl == "note"]
    assert any(t.startswith(f"zone exposée {DMZ} : gardé(s) protégé(s)") and FRONT in t and FW in t for t in notes)
    assert any(t.startswith(f"zone exposée {PARTNER} : gardé(s) protégé(s)") and NAT_IP in t for t in notes)
    assert any(t.startswith("zone exposée 10.2.0.0/24 en plage privée : la règle livrée") for t in notes)
    assert ("zone exposée, réseau nommé « big » : 10.16.0.0/12 écartée — plus large que /16 : une zone exposée "
            "ou une origine attendue est étroite") in " ".join(notes)
    assert protection("10.16.0.9").layer == CLIENT                            # left out: never blocked
    assert not any(t.startswith("chevauchement") and "zone exposée" in t and "VNet" in t for t in notes)
    assert not [t for lvl, t in lines if lvl == "loud"]


def test_the_watch_prints_a_zone_in_bold(cfg_file):
    from rich.console import Console
    from glorfindel.watch.networks import _STYLE, say_networks
    _saved()
    console = Console(record=True, width=400)
    say_networks(console, dry_run=False)
    assert f"▲ Zone exposée {DMZ}" in console.export_text()
    assert "bold" in _STYLE["strong"]


# ── The review of SEC2b, its six points ──────────────────────────────────────────────────────

def test_a_list_that_can_t_be_written_is_said_so_by_the_guard_of_the_watch(cfg_file):
    """M7195 (point 1): the write failed in this process — the guard reads « non écrite », never « jamais
    lue », and an older fresh file on disk is no fresh list."""
    import os
    cn._STORE.parent.mkdir(parents=True, exist_ok=True)
    os.chmod(cn._STORE.parent, 0o555)
    try:
        cnw.refresh(lambda: _read(), config.load_glorfindel_config())
    finally:
        os.chmod(cn._STORE.parent, 0o755)
    assert "liste non écrite" in protection("10.9.9.9").degraded and "jamais lue" not in protection("10.9.9.9").degraded
    cnw.refresh(lambda: _read(), config.load_glorfindel_config())
    assert cn.load().state == "fresh"                                         # written: the mark cleared
    os.chmod(cn._STORE, 0o444)
    os.chmod(cn._STORE.parent, 0o555)
    try:
        cnw.refresh(lambda: _read(), config.load_glorfindel_config())
    finally:
        os.chmod(cn._STORE.parent, 0o755)
        os.chmod(cn._STORE, 0o644)
    snap = cn.load()
    assert snap.state == "failed" and "liste non écrite" in snap.degraded() and snap.read_at


def test_a_kept_that_is_no_table_never_breaks_a_partial_read(cfg_file):
    """Point 2."""
    import json
    _saved()
    body = json.loads(cn._STORE.read_text())
    body["kept"] = ["not", "a", "table"]
    cn._STORE.write_text(json.dumps(body))
    snap = cn.save({**_read(), "unread": [{"what": "IP publiques", "key": "public_ips", "error": "429"}],
                    "public_ips": []}, datetime.now(timezone.utc))
    assert snap.state == "partial" and {p["address"] for p in snap.public_ips} == {NAT_IP, WEB_IP, FW_IP}


def test_the_files_doc_lists_kept():
    """Point 3."""
    from pathlib import Path
    doc = (Path(__file__).resolve().parents[2] / "docs" / "fichiers-cles.md").read_text()
    line = next(x for x in doc.splitlines() if "network/client_network.json" in x and "`read_at`" in x)
    assert "`kept`" in line and "`nics`" in line


def test_the_makefile_checks_the_network_directory_can_be_written():
    """Point 4: made, then its writing checked, before compose — in RUNS_DIRS and in team-start."""
    from pathlib import Path
    make = (Path(__file__).resolve().parents[2] / "Makefile").read_text()
    runs = make.split("RUNS_DIRS =", 1)[1].split("\n#", 1)[0]
    assert runs.index("mkdir -p runs/glorfindel/queue runs/glorfindel/network") < runs.index(
        "test -w runs/glorfindel/network")
    team = make.split("\nteam-start:", 1)[1].split("\n\n", 1)[0]
    assert (team.index('mkdir -p "$(TEAM_DIR)/runs/glorfindel/network"')
            < team.index('test -w "$(TEAM_DIR)/runs/glorfindel/network"') < team.index("up -d watch war-room"))


def test_an_unblock_written_as_ipv6_finds_the_entry_noted_under_its_ipv4(cfg_file, azure):
    """Point 5: `::ffff:a.b.c.d` lifts the block of a.b.c.d — and an address protected since stays liftable."""
    f, c, nsg = azure
    before = _rules(f, nsg)
    c.block_suspicious_ip(INTERNET, vm_id("rg-app", "web"))
    cfg_file.write_text(f"never_block: [{INTERNET}]\n")                         # protected since the block
    out = c.unblock_ip(f"::ffff:{INTERNET}", vm_id("rg-app", "web"))
    assert out["status"] == "unblocked" and _entry(INTERNET) == {} and _rules(f, nsg) == before


def test_a_whole_read_with_no_vnet_is_said_once_per_change(cfg_file, caplog):
    """Point 6: said at the first read, not at each read after it; said again once it changes."""
    from glorfindel.discovery import AssetRegistry, DiscoveredAsset
    AssetRegistry().update([DiscoveredAsset(name="web", resource_id=vm_id("rg-app", "web"),
                                            monitoring_backend="law",
                                            last_seen=datetime.now(timezone.utc).isoformat())])
    cfg = config.GlorfindelConfig()
    empty = {**_read(), "vnets": []}
    cnw._SAID.clear()
    with caplog.at_level(logging.WARNING, logger="glorfindel.client_network"):
        for _ in range(3):
            cnw.refresh(lambda: empty, cfg)
        cnw.refresh(lambda: _read(), cfg)
        cnw.refresh(lambda: empty, cfg)
    assert sum("sans aucun VNet" in r.getMessage() for r in caplog.records) == 2
